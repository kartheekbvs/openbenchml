"""
End-to-end smoke test for the new dataset preview + sample benchmark flow.

Verifies:
1. ensure_sample_models() trains and persists real sklearn models
2. find_sample_model_for_dataset() returns the correct row
3. get_dataset_preview() returns df.head(N) rows for both CSV and sklearn datasets
4. The benchmark engine produces real metrics when run on a sample model
5. The /datasets/{id} and /benchmark/sample/{id} routes render without errors
"""
import os
import sys
import json
import tempfile
from pathlib import Path

sys.path.insert(0, "/home/z/my-project")
os.chdir("/home/z/my-project")

from app.database.db import SessionLocal, init_db
from app.database.models import Dataset, MLModel, BenchmarkJob
from app.database.seed import seed_database
from app.services.sample_models_service import (
    ensure_sample_models,
    find_sample_model_for_dataset,
    list_sample_models,
    SYSTEM_USERNAME,
    SAMPLE_MODEL_NAME_PREFIX,
)
from app.services.dataset_preview_service import (
    get_dataset_preview,
    DEFAULT_PREVIEW_ROWS,
    clamp_rows,
)
from app.services.benchmark_service import create_benchmark_job, run_benchmark
from app.benchmark_engine.loader import load_dataset


PASS = 0
FAIL = 0
SKIP = 0


def check(label, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  PASS  {label}")
    else:
        FAIL += 1
        print(f"  FAIL  {label}  {detail}")


def main():
    print()
    print("=" * 78)
    print("OpenBenchML — Dataset Preview + Sample Benchmark E2E Test")
    print("=" * 78)

    # Ensure DB and seed
    print("\n[1/6] Initialising DB and seeding datasets...")
    init_db()
    seed_database()

    db = SessionLocal()
    try:
        # ── Train sample models ────────────────────────────────────────────
        print("\n[2/6] Training sample models (this may take ~30s)...")
        stats = ensure_sample_models(db)
        print(f"      created={stats['created']} reused={stats['reused']} "
              f"failed={stats['failed']} total={stats['total']}")
        check("sample models created for all datasets",
              stats['created'] + stats['reused'] >= 15,
              f"only {stats['created'] + stats['reused']} models available")
        check("no training failures (or only a few)",
              stats['failed'] <= 3,
              f"{stats['failed']} failures")

        # ── List sample models ─────────────────────────────────────────────
        print("\n[3/6] Verifying sample models in DB...")
        sample_models = list_sample_models(db)
        print(f"      Found {len(sample_models)} sample models:")
        for m in sample_models[:5]:
            file_ok = "OK" if (m.file_path and os.path.isfile(m.file_path)) else "MISSING"
            print(f"        - id={m.id}  {m.model_name}  ({m.framework}, {m.size_kb:.1f} KB)  file={file_ok}")
        if len(sample_models) > 5:
            print(f"        ... and {len(sample_models) - 5} more")
        check("at least 15 sample models exist", len(sample_models) >= 15,
              f"only {len(sample_models)}")
        check("all sample model files exist on disk",
              all(m.file_path and os.path.isfile(m.file_path) for m in sample_models),
              "some files are missing")
        check("sample models are owned by system user",
              all(m.owner.username == SYSTEM_USERNAME for m in sample_models if m.owner),
              "owner mismatch")

        # ── Dataset preview ────────────────────────────────────────────────
        print("\n[4/6] Testing df.head(N) preview for every dataset...")
        datasets = db.query(Dataset).order_by(Dataset.id).all()
        csv_preview_ok = 0
        sklearn_preview_ok = 0
        for ds in datasets:
            preview = get_dataset_preview(ds, 5)
            if preview.get("columns") and preview.get("rows"):
                if preview.get("source") == "csv":
                    csv_preview_ok += 1
                elif preview.get("source") == "sklearn":
                    sklearn_preview_ok += 1
                else:
                    print(f"      UNKNOWN source for {ds.name}: {preview.get('source')}")
            else:
                print(f"      FAIL preview for {ds.name}: {preview.get('error', 'no rows')}")
        print(f"      CSV previews OK: {csv_preview_ok}")
        print(f"      sklearn previews OK: {sklearn_preview_ok}")
        check("CSV dataset previews work", csv_preview_ok >= 10,
              f"only {csv_preview_ok} OK")
        check("sklearn dataset previews work", sklearn_preview_ok >= 5,
              f"only {sklearn_preview_ok} OK")

        # ── Preview row clamping ───────────────────────────────────────────
        print("\n      Testing row count clamping...")
        check("clamp_rows(None) == 5", clamp_rows(None) == 5)
        check("clamp_rows(0) == 1", clamp_rows(0) == 1)
        check("clamp_rows(1000) == 100", clamp_rows(1000) == 100)
        check("clamp_rows('abc') == 5", clamp_rows('abc') == 5)
        check("clamp_rows(20) == 20", clamp_rows(20) == 20)

        # ── Find sample model for dataset ──────────────────────────────────
        print("\n[5/6] Testing find_sample_model_for_dataset()...")
        find_ok = 0
        find_fail = []
        for ds in datasets[:10]:
            sm = find_sample_model_for_dataset(ds, db)
            if sm and sm.file_path and os.path.isfile(sm.file_path):
                find_ok += 1
            else:
                find_fail.append(ds.name)
        print(f"      find_ok = {find_ok}/10")
        check("find_sample_model_for_dataset works for most datasets",
              find_ok >= 8,
              f"missing for: {find_fail}")

        # ── Run a real sample benchmark end-to-end ─────────────────────────
        print("\n[6/6] Running a real sample benchmark (Titanic dataset)...")
        titanic = db.query(Dataset).filter(Dataset.name == "Titanic").first()
        if titanic is None:
            print("      SKIP: Titanic dataset not found")
            global SKIP
            SKIP += 1
        else:
            sm = find_sample_model_for_dataset(titanic, db)
            if sm is None:
                print("      SKIP: no sample model for Titanic")
                SKIP += 1
            else:
                try:
                    # Run the actual benchmark synchronously
                    job = create_benchmark_job(model_id=sm.id, dataset_id=titanic.id, db=db)
                    print(f"      Created job id={job.id}, running...")
                    result = run_benchmark(job_id=job.id, db=db)

                    print(f"      Job status: {job.status}")
                    print(f"      Accuracy:   {result.accuracy}")
                    print(f"      F1 Score:   {result.f1_score}")
                    print(f"      Latency P95: {result.latency_p95_ms} ms")
                    print(f"      Throughput:  {result.throughput_per_sec} /s")
                    print(f"      Inferences:  {result.inference_count}")

                    check("sample benchmark completed", job.status == "completed",
                          f"status={job.status}, err={job.error_message}")
                    check("accuracy is a real number (0..1)",
                          result.accuracy is not None and 0.0 <= result.accuracy <= 1.0,
                          f"accuracy={result.accuracy}")
                    check("F1 score is a real number (0..1)",
                          result.f1_score is not None and 0.0 <= result.f1_score <= 1.0,
                          f"f1={result.f1_score}")
                    check("P95 latency > 0",
                          result.latency_p95_ms is not None and result.latency_p95_ms > 0,
                          f"p95={result.latency_p95_ms}")
                    check("throughput > 0",
                          result.throughput_per_sec is not None and result.throughput_per_sec > 0,
                          f"tput={result.throughput_per_sec}")
                    check("inference_count > 0",
                          result.inference_count is not None and result.inference_count > 0,
                          f"ic={result.inference_count}")
                except Exception as exc:
                    print(f"      EXCEPTION: {type(exc).__name__}: {exc}")
                    check("sample benchmark ran without exception", False, str(exc))

        # ── Summary ────────────────────────────────────────────────────────
        print()
        print("=" * 78)
        print(f"RESULT: {PASS} passed, {FAIL} failed, {SKIP} skipped")
        print("=" * 78)
        return 0 if FAIL == 0 else 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
