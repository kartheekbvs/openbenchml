"""
OpenBenchML Docker Sandbox Runner
====================================
Provides secure, containerised execution of ML model benchmarks.

The :class:`DockerRunner` spins up an ephemeral Docker container
(from the ``openbenchml-worker`` image), mounts the model file
read-only, passes configuration through environment variables, waits
for the container to finish, and parses the JSON result printed to
stdout.

If Docker is unavailable (common in local development), a fallback
path runs the evaluation directly in the host process.

Public API
----------

* :class:`DockerRunner`  – main runner class
* :func:`is_docker_available` – probe the Docker daemon
"""

import json
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from app.config import DOCKER_IMAGE, DOCKER_TIMEOUT, BENCHMARK_TIMEOUT_SECONDS

logger = logging.getLogger(__name__)


# ─── Docker availability check ─────────────────────────────────────────────────

def is_docker_available() -> bool:
    """Check whether the Docker daemon is reachable.

    Attempts to instantiate a Docker client and ping the daemon.  Returns
    ``True`` if the daemon responds, ``False`` otherwise (e.g. Docker not
    installed, daemon not running, permission denied).

    Returns:
        ``True`` if the Docker daemon is reachable, ``False`` otherwise.
    """
    try:
        import docker  # noqa: F401 – imported only to check availability

        client = docker.from_env()
        client.ping()
        client.close()
        logger.info("Docker daemon is available")
        return True
    except ImportError:
        logger.warning("Python 'docker' package is not installed")
        return False
    except Exception as exc:
        logger.warning("Docker daemon is not reachable: %s", exc)
        return False


# ─── DockerRunner class ────────────────────────────────────────────────────────

class DockerRunner:
    """Execute ML benchmarks inside ephemeral Docker containers.

    Each call to :meth:`run_benchmark_in_container` creates a fresh
    container, mounts the model file read-only, injects configuration
    via environment variables, waits for completion (with a timeout),
    parses JSON output from the container logs, and tears down the
    container.

    Attributes:
        image_name: Name/tag of the Docker image to run.
        timeout: Maximum wall-clock seconds to wait for the container.
        client: A ``docker.DockerClient`` instance (``None`` if Docker
            is unavailable).
    """

    def __init__(self) -> None:
        """Initialize the Docker runner.

        Creates a Docker client from environment variables.  If the
        client cannot be created (Docker not installed or daemon not
        running), ``self.client`` is set to ``None`` and a warning is
        logged.  In that state only the fallback (direct) execution
        path is available.
        """
        self.image_name: str = DOCKER_IMAGE
        self.timeout: int = DOCKER_TIMEOUT

        try:
            import docker
            self.client = docker.from_env()
            # Verify the daemon is reachable.
            self.client.ping()
            logger.info(
                "DockerRunner initialised (image=%s, timeout=%ds)",
                self.image_name,
                self.timeout,
            )
        except Exception as exc:
            self.client = None
            logger.warning(
                "Docker client could not be created: %s. "
                "Falling back to direct execution.",
                exc,
            )

    # ─── Main execution method ─────────────────────────────────────────────

    def run_benchmark_in_container(
        self,
        model_path: str,
        framework: str,
        dataset_name: str,
        job_id: int,
        task_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Run a benchmark inside a Docker container.

        Creates a container from the configured worker image, mounts the
        model file read-only, sets environment variables for the worker
        script, waits for completion, and parses the JSON result from
        the container's stdout.

        If Docker is unavailable the method transparently falls back to
        running the evaluation directly in the host process (useful for
        local development).

        Args:
            model_path: Absolute path to the model file on the host.
            framework: Framework identifier (e.g. ``"scikit-learn"``).
            dataset_name: Name of a built-in dataset or path to a custom
                dataset file.
            job_id: Benchmark job identifier (for logging / tracing).
            task_type: Optional task type override (``classification``
                or ``regression``).  Defaults to ``None`` (auto-detect).

        Returns:
            A dictionary of benchmark results as produced by the worker
            script (metrics, performance data, etc.).

        Raises:
            FileNotFoundError: If the model file does not exist.
            RuntimeError: If the container fails, times out, or produces
                invalid output, **and** the fallback also fails.
        """
        # ── Validate model file ────────────────────────────────────────────
        if not os.path.isfile(model_path):
            raise FileNotFoundError(f"Model file not found: {model_path}")

        # ── Docker path ────────────────────────────────────────────────────
        if self.client is not None:
            return self._run_in_docker(
                model_path, framework, dataset_name, job_id, task_type
            )

        # ── Fallback: direct execution ─────────────────────────────────────
        logger.warning(
            "Docker unavailable – running benchmark job_id=%d directly "
            "in the host process (development fallback)",
            job_id,
        )
        return self._run_directly(
            model_path, framework, dataset_name, task_type
        )

    # ─── Docker execution ──────────────────────────────────────────────────

    def _run_in_docker(
        self,
        model_path: str,
        framework: str,
        dataset_name: str,
        job_id: int,
        task_type: Optional[str],
    ) -> Dict[str, Any]:
        """Execute the benchmark inside a Docker container.

        Args:
            model_path: Host path to the model file.
            framework: ML framework identifier.
            dataset_name: Dataset name or path.
            job_id: Job identifier (for logging).
            task_type: Optional task type override.

        Returns:
            Parsed results dictionary from container stdout.

        Raises:
            RuntimeError: On container failure, timeout, or bad output.
        """
        import docker

        container = None
        container_name = f"openbenchml-job-{job_id}"

        # Resolve the mount path: the model is mounted at /app/model inside
        # the container.
        host_model_path = os.path.abspath(model_path)
        container_model_path = "/app/model"

        # Resolve dataset path for volume mount (if it is a file on disk).
        volumes: Dict[str, Dict[str, str]] = {
            host_model_path: {"bind": container_model_path, "mode": "ro"},
        }

        # If dataset_name points to a file, mount it read-only as well.
        dataset_container_path = dataset_name
        if os.path.isfile(dataset_name):
            host_dataset_path = os.path.abspath(dataset_name)
            dataset_container_path = "/app/dataset"
            volumes[host_dataset_path] = {
                "bind": dataset_container_path,
                "mode": "ro",
            }

        # Build environment variables for the worker script.
        environment: Dict[str, str] = {
            "MODEL_PATH": container_model_path,
            "FRAMEWORK": framework,
            "DATASET_NAME": dataset_container_path,
        }
        if task_type:
            environment["TASK_TYPE"] = task_type

        try:
            logger.info(
                "Creating container '%s' (image=%s, model=%s, framework=%s, "
                "dataset=%s)",
                container_name,
                self.image_name,
                container_model_path,
                framework,
                dataset_container_path,
            )

            container = self.client.containers.run(
                image=self.image_name,
                name=container_name,
                volumes=volumes,
                environment=environment,
                detach=True,
                stdout=True,
                stderr=True,
                remove=False,  # We remove manually after reading logs.
                network_mode="none",  # Isolate from network.
                mem_limit="2g",
                cpu_period=100000,
                cpu_quota=90000,  # 90 % of one CPU
                pids_limit=256,
            )

            logger.info("Container '%s' started (id=%s)", container_name, container.short_id)

            # ── Wait for container to finish ────────────────────────────────
            result = container.wait(timeout=self.timeout)
            exit_code = result.get("StatusCode", -1)

            # ── Fetch logs ──────────────────────────────────────────────────
            logs = container.logs(stdout=True, stderr=False).decode("utf-8", errors="replace")
            stderr_logs = container.logs(stdout=False, stderr=True).decode("utf-8", errors="replace")

            if stderr_logs.strip():
                logger.debug(
                    "Container '%s' stderr:\n%s",
                    container_name,
                    stderr_logs[:2000],
                )

            if exit_code != 0:
                logger.error(
                    "Container '%s' exited with code %d. stdout:\n%s",
                    container_name,
                    exit_code,
                    logs[:2000],
                )
                raise RuntimeError(
                    f"Benchmark container for job_id={job_id} exited with "
                    f"code {exit_code}. Output: {logs[:500]}"
                )

            # ── Parse JSON output ───────────────────────────────────────────
            results = self._parse_container_output(logs, job_id)
            logger.info(
                "Container '%s' completed successfully (job_id=%d)",
                container_name,
                job_id,
            )
            return results

        except docker.errors.ImageNotFound:
            raise RuntimeError(
                f"Docker image '{self.image_name}' not found. "
                f"Run DockerRunner.build_worker_image() first."
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError(
                f"Benchmark container for job_id={job_id} timed out "
                f"after {self.timeout} seconds"
            )
        except RuntimeError:
            raise
        except Exception as exc:
            raise RuntimeError(
                f"Benchmark container for job_id={job_id} failed: {exc}"
            ) from exc

        finally:
            # ── Clean up container ──────────────────────────────────────────
            if container is not None:
                try:
                    container.remove(force=True)
                    logger.debug("Container '%s' removed", container_name)
                except Exception as cleanup_exc:
                    logger.warning(
                        "Failed to remove container '%s': %s",
                        container_name,
                        cleanup_exc,
                    )

    # ─── Direct execution fallback ─────────────────────────────────────────

    def _run_directly(
        self,
        model_path: str,
        framework: str,
        dataset_name: str,
        task_type: Optional[str],
    ) -> Dict[str, Any]:
        """Run the evaluation directly in the host process.

        This is a development fallback that bypasses Docker entirely.
        It reuses the same :func:`evaluate_model` entry point that the
        worker script uses, so the results should be identical.

        Args:
            model_path: Path to the model file.
            framework: ML framework identifier.
            dataset_name: Dataset name or path.
            task_type: Optional task type override.

        Returns:
            Results dictionary from the evaluation.

        Raises:
            RuntimeError: If the evaluation fails.
        """
        from app.benchmark_engine.evaluator import evaluate_model

        try:
            logger.info(
                "Running benchmark directly (model=%s, framework=%s, "
                "dataset=%s, task_type=%s)",
                model_path,
                framework,
                dataset_name,
                task_type,
            )
            results = evaluate_model(
                model_path=model_path,
                framework=framework,
                dataset_name=dataset_name,
                task_type=task_type,
                timeout_seconds=BENCHMARK_TIMEOUT_SECONDS,
            )
            return results
        except Exception as exc:
            raise RuntimeError(
                f"Direct benchmark execution failed: {exc}"
            ) from exc

    # ─── Build the worker image ────────────────────────────────────────────

    def build_worker_image(self) -> bool:
        """Build the Docker worker image from the project Dockerfile.

        Looks for a ``Dockerfile`` in the ``docker_runner`` package
        directory and builds an image tagged with
        ``self.image_name`` (``openbenchml-worker`` by default).

        Returns:
            ``True`` if the image was built successfully, ``False``
            otherwise (including when Docker is unavailable).
        """
        if self.client is None:
            logger.error("Cannot build image: Docker client is not available")
            return False

        dockerfile_dir = str(Path(__file__).resolve().parent)
        dockerfile_path = os.path.join(dockerfile_dir, "Dockerfile")

        if not os.path.isfile(dockerfile_path):
            logger.error("Dockerfile not found at %s", dockerfile_path)
            return False

        try:
            logger.info(
                "Building Docker image '%s' from %s",
                self.image_name,
                dockerfile_dir,
            )
            image, build_logs = self.client.images.build(
                path=dockerfile_dir,
                tag=self.image_name,
                rm=True,
                forcerm=True,
            )

            # Log build output at debug level.
            for log_entry in build_logs:
                if "stream" in log_entry:
                    logger.debug(log_entry["stream"].rstrip())
                elif "error" in log_entry:
                    logger.error("Build error: %s", log_entry["error"])

            logger.info(
                "Docker image '%s' built successfully (id=%s)",
                self.image_name,
                image.short_id,
            )
            return True

        except Exception as exc:
            logger.error("Failed to build Docker image '%s': %s", self.image_name, exc)
            return False

    # ─── Cleanup stopped containers ────────────────────────────────────────

    def cleanup(self) -> int:
        """Remove all stopped OpenBenchML containers.

        Containers whose names start with ``openbenchml-job-`` and are
        in a non-running state are pruned.  This is safe to call
        periodically to avoid accumulating stale containers.

        Returns:
            The number of containers removed.
        """
        if self.client is None:
            logger.warning("Cannot cleanup: Docker client is not available")
            return 0

        removed = 0
        try:
            containers = self.client.containers.list(
                all=True,
                filters={"name": "openbenchml-job-"},
            )
            for container in containers:
                if container.status != "running":
                    try:
                        container.remove()
                        removed += 1
                        logger.debug("Removed stopped container: %s", container.name)
                    except Exception as exc:
                        logger.warning(
                            "Failed to remove container %s: %s",
                            container.name,
                            exc,
                        )

            if removed:
                logger.info("Cleaned up %d stopped container(s)", removed)
            else:
                logger.debug("No stopped containers to clean up")

        except Exception as exc:
            logger.error("Cleanup failed: %s", exc)

        return removed

    # ─── Output parsing ────────────────────────────────────────────────────

    @staticmethod
    def _parse_container_output(output: str, job_id: int) -> Dict[str, Any]:
        """Parse JSON output from the container's stdout.

        The worker script prints a single JSON object to stdout.  Any
        leading/trailing non-JSON text (e.g. log lines) is ignored –
        only the last valid JSON object on stdout is used.

        Args:
            output: Raw stdout from the container.
            job_id: Job identifier (for error messages).

        Returns:
            Parsed results dictionary.

        Raises:
            RuntimeError: If no valid JSON can be extracted.
        """
        output = output.strip()
        if not output:
            raise RuntimeError(
                f"Benchmark container for job_id={job_id} produced no output"
            )

        # Try direct parse first (fast path).
        try:
            return json.loads(output)
        except json.JSONDecodeError:
            pass

        # Slow path: scan for the last valid JSON object in the output.
        # The worker may emit log lines before the result JSON.
        best_result: Optional[Dict[str, Any]] = None
        decoder = json.JSONDecoder()
        idx = 0
        while idx < len(output):
            # Find the next '{' character.
            brace_pos = output.find("{", idx)
            if brace_pos == -1:
                break
            try:
                obj, end = decoder.raw_decode(output, brace_pos)
                if isinstance(obj, dict):
                    best_result = obj
                idx = end
            except json.JSONDecodeError:
                idx = brace_pos + 1

        if best_result is not None:
            return best_result

        raise RuntimeError(
            f"Could not parse JSON output from container for job_id={job_id}. "
            f"Raw output (first 500 chars): {output[:500]}"
        )
