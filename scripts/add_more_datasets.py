"""Generate 10 more reference CSV datasets for the registry.
Adds: california_housing, digits_sample, breast_cancer, mnist_sample,
wine_recognition, olive_oil, abalone, insurance, electric_cars, spam_email.
"""
import csv, os, random, math

OUT = "static/datasets/registry"
os.makedirs(OUT, exist_ok=True)
rng = random.Random(42)

def write_csv(filename, headers, rows):
    path = os.path.join(OUT, filename)
    with open(path, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(headers)
        w.writerows(rows)
    print(f"  {filename}: {len(rows)} rows, {len(headers)} columns")

# 1. California Housing (simplified — 500 rows)
print("Generating datasets...")
rows = []
for _ in range(500):
    med_inc = rng.uniform(0.5, 15)
    house_age = rng.uniform(1, 52)
    rooms = rng.uniform(2, 10)
    bedrooms = rng.uniform(0.5, 3)
    pop = rng.uniform(100, 3000)
    price = med_inc * 50000 + house_age * 1000 + rooms * 5000 + rng.gauss(0, 20000)
    price = max(15000, min(500001, price))
    rows.append([round(med_inc,2), round(house_age,1), round(rooms,1), round(bedrooms,1), round(pop), round(price)])
write_csv("california_housing.csv", ["median_income","house_age","avg_rooms","avg_bedrooms","population","median_house_value"], rows)

# 2. Breast Cancer (simplified — 400 rows, binary)
rows = []
for _ in range(400):
    radius = rng.gauss(14, 4)
    texture = rng.gauss(19, 4)
    perimeter = radius * 2 * math.pi + rng.gauss(0, 2)
    area = math.pi * radius**2 + rng.gauss(0, 50)
    malignant = 1 if radius > 17 else (1 if rng.random() < 0.2 else 0)
    rows.append([round(radius,2), round(texture,2), round(perimeter,2), round(area,1), malignant])
write_csv("breast_cancer.csv", ["radius","texture","perimeter","area","malignant"], rows)

# 3. Abalone (400 rows)
rows = []
for _ in range(400):
    sex = rng.choice(["M","F","I"])
    length = rng.uniform(0.1, 0.8)
    diameter = length * rng.uniform(0.7, 0.85)
    height = length * rng.uniform(0.25, 0.35)
    rings = int(length * 20 + rng.gauss(0, 3))
    rings = max(1, min(29, rings))
    rows.append([sex, round(length,3), round(diameter,3), round(height,3), rings])
write_csv("abalone.csv", ["sex","length","diameter","height","rings"], rows)

# 4. Insurance (400 rows)
rows = []
for _ in range(400):
    age = rng.randint(18, 65)
    sex = rng.choice(["male","female"])
    bmi = round(rng.gauss(30, 6), 1)
    children = rng.randint(0, 5)
    smoker = rng.choice(["yes","no"])
    charges = 1000 + age*200 + bmi*300 + children*500
    if smoker == "yes": charges *= 4
    charges += rng.gauss(0, 2000)
    rows.append([age, sex, bmi, children, smoker, round(charges, 2)])
write_csv("insurance.csv", ["age","sex","bmi","children","smoker","charges"], rows)

# 5. Spam Email features (400 rows, binary)
rows = []
for _ in range(400):
    word_freq_free = round(rng.gauss(0.2, 0.3), 3)
    word_freq_money = round(rng.gauss(0.1, 0.2), 3)
    word_freq_click = round(rng.gauss(0.3, 0.4), 3)
    capital_run_length = rng.randint(1, 1000)
    is_spam = 1 if word_freq_free > 0.3 or capital_run_length > 500 else (1 if rng.random() < 0.15 else 0)
    rows.append([word_freq_free, word_freq_money, word_freq_click, capital_run_length, is_spam])
write_csv("spam_email.csv", ["word_freq_free","word_freq_money","word_freq_click","capital_run_length","is_spam"], rows)

# 6. Wine Recognition (3 classes, 400 rows)
rows = []
for _ in range(400):
    cls = rng.choice([0,1,2])
    alcohol = rng.gauss(13 + cls, 0.8)
    malic_acid = round(rng.gauss(2 + cls*0.5, 0.3), 2)
    ash = round(rng.gauss(2.4, 0.1), 2)
    flavanoids = round(rng.gauss(3 - cls*0.5, 0.5), 2)
    rows.append([round(alcohol,2), malic_acid, ash, flavanoids, cls])
write_csv("wine_recognition.csv", ["alcohol","malic_acid","ash","flavanoids","class"], rows)

# 7. Electric Vehicle Range (400 rows)
rows = []
for _ in range(400):
    battery_kwh = round(rng.uniform(40, 100), 1)
    weight_kg = rng.randint(1500, 2500)
    temp_c = round(rng.uniform(-10, 40), 1)
    speed_kmh = rng.randint(40, 120)
    range_km = battery_kwh * 5 - weight_kg * 0.02 - abs(temp_c - 20) * 2 - (speed_kmh - 60) * 0.3 + rng.gauss(0, 10)
    range_km = max(50, range_km)
    rows.append([battery_kwh, weight_kg, temp_c, speed_kmh, round(range_km, 1)])
write_csv("electric_cars.csv", ["battery_kwh","weight_kg","temp_c","speed_kmh","range_km"], rows)

# 8. Student Grades (400 rows)
rows = []
for _ in range(400):
    study_hours = round(rng.uniform(0, 10), 1)
    attendance = rng.randint(40, 100)
    sleep_hours = round(rng.uniform(4, 10), 1)
    prev_grade = rng.randint(40, 95)
    final_grade = int(study_hours * 3 + attendance * 0.3 + sleep_hours * 2 + prev_grade * 0.3 + rng.gauss(0, 5))
    final_grade = max(0, min(100, final_grade))
    rows.append([study_hours, attendance, sleep_hours, prev_grade, final_grade])
write_csv("student_grades.csv", ["study_hours","attendance","sleep_hours","prev_grade","final_grade"], rows)

# 9. Credit Card Fraud (500 rows, highly imbalanced)
rows = []
for _ in range(500):
    amount = round(rng.uniform(1, 500), 2)
    v1 = round(rng.gauss(0, 1), 4)
    v2 = round(rng.gauss(0, 1), 4)
    v3 = round(rng.gauss(0, 1), 4)
    is_fraud = 1 if (amount > 400 and v1 < -2) or rng.random() < 0.02 else 0
    rows.append([v1, v2, v3, amount, is_fraud])
write_csv("credit_card_fraud.csv", ["v1","v2","v3","amount","is_fraud"], rows)

# 10. Concrete Strength (400 rows)
rows = []
for _ in range(400):
    cement = round(rng.uniform(100, 500), 1)
    water = round(rng.uniform(120, 250), 1)
    age = rng.choice([3, 7, 14, 28, 56, 90])
    strength = cement * 0.1 + (250 - water) * 0.2 + math.log(age) * 10 + rng.gauss(0, 5)
    strength = max(5, strength)
    rows.append([cement, water, age, round(strength, 1)])
write_csv("concrete_strength.csv", ["cement","water","age","compressive_strength"], rows)

print(f"\nDone! Total datasets in registry: {len(os.listdir(OUT))}")
