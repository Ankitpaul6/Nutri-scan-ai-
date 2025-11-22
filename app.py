from flask import Flask, request, jsonify
import pandas as pd
import requests
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

USDA_API_KEY = "R838HbXtFPgM8SxiaWbOmWgii2KtvsaVV3WAdcNA"

# ------------------------------------------------------------
# Load your local Excel database safely
# ------------------------------------------------------------
def load_food_db():
    try:
        df = pd.read_excel("foods_db.xlsx", engine="openpyxl")
        print(f"✅ Loaded local DB: {len(df)} entries")
        return df
    except Exception as e:
        print("⚠️ Error loading Excel file:", e)
        return pd.DataFrame()

food_db = load_food_db()

# ------------------------------------------------------------
@app.route('/')
def home():
    return "🍎 NutriScan Backend Running (Local DB → OpenFoodFacts → USDA) 🚀"

# ------------------------------------------------------------
# Smart health label + fitness tips
# ------------------------------------------------------------
def get_health_label_and_tips(nutrition):
    try:
        protein = float(str(nutrition.get("protein", "0")).split()[0])
        fat = float(str(nutrition.get("fat", "0")).split()[0])
        sugar = float(str(nutrition.get("sugar", "0")).split()[0])
    except:
        protein, fat, sugar = 0, 0, 0

    if protein >= 7 and fat <3 and sugar <= 4:
        label, color = "Good", "green"
        tips = [
            "High protein, low sugar — excellent for muscle recovery.",  
            "Perfect post-workout fuel that keeps energy stable.",
            "Pair with complex carbs and water for max recovery.",
            "Add fiber-rich foods for longer satiety.",
            "Keep tracking macros — you’re smashing it!"
        ]
    elif protein >= 8 or (fat <= 9 or sugar <= 9):
        label, color = "Moderate", "orange"
        tips = [
            "Good for one time intake .",
            "Fine as quick meal not recomended to repeat this same meal in a day.",
            "Avoid if goal is cutting calories.",
            "Strictly Not recommended for diabetes patient",
            "Stay hydrated for better endurance."
        ]
    else:
        label, color = "Bad", "red"
        tips = [
            "High sugar or fat — enjoy rarely.",
            "Pick leaner or less processed options.",
            "Combine with protein to balance energy spikes.",
            "Avoid late-night intake to stay lean.",
            "AVOID AVOID"
        ]
    return label, color, tips

# ------------------------------------------------------------
# 1️⃣ Always check LOCAL DB first
# ------------------------------------------------------------
def fetch_from_local_db(barcode):
    try:
        row = food_db.loc[food_db['barcode'].astype(str) == str(barcode)]
        if not row.empty:
            item = row.iloc[0]
            nutrition = {
                "protein": f"{item.get('protein', 0)} g",
                "carbs": f"{item.get('carbs', 0)} g",
                "fat": f"{item.get('fat', 0)} g",
                "fiber": f"{item.get('fiber', 0)} g",
                "sugar": f"{item.get('sugar', 0)} g",
                "calories": f"{item.get('calories', 0)} kcal"
            }
            label, color, tips = get_health_label_and_tips(nutrition)
            eco = str(item.get("ecoscore", "N/A")).upper()
            nutri = str(item.get("nutriscore", "N/A")).upper()

            return {
                "source": "Local Excel DB ✅",
                "barcode": barcode,
                "product": item.get("product_name", "Unknown Product"),
                "nutrition": nutrition,
                "ecoscore": eco,
                "ecoscoreColor": "green" if eco in ["A", "B"]
                                   else "orange" if eco == "C" else "red",
                "nutriscore": nutri,
                "nutriscoreColor": "green" if nutri in ["A", "B"]
                                    else "orange" if nutri == "C" else "red",
                "healthLabel": label,
                "healthLabelColor": color,
                "tips": tips
            }
    except Exception as e:
        print("⚠️ Local DB fetch error:", e)
    return None

# ------------------------------------------------------------
# 2️⃣ Open Food Facts fallback
# ------------------------------------------------------------
def fetch_from_openfoodfacts(barcode):
    urls = [
        f"https://world.openfoodfacts.org/api/v0/product/{barcode}.json",
        f"https://in.openfoodfacts.org/api/v0/product/{barcode}.json",
        f"https://us.openfoodfacts.org/api/v0/product/{barcode}.json"
    ]
    for url in urls:
        try:
            res = requests.get(url, timeout=6)
            data = res.json()
            if data.get("status") == 1:
                product = data["product"]
                n = product.get("nutriments", {})
                nutrition = {
                    "protein": f"{n.get('proteins_100g', 0)} g",
                    "carbs": f"{n.get('carbohydrates_100g', 0)} g",
                    "fat": f"{n.get('fat_100g', 0)} g",
                    "fiber": f"{n.get('fiber_100g', 0)} g",
                    "sugar": f"{n.get('sugars_100g', 0)} g",
                    "calories": f"{n.get('energy-kcal_100g', 0)} kcal"
                }
                label, color, tips = get_health_label_and_tips(nutrition)
                eco = product.get("ecoscore_grade", "N/A").upper()
                nutri = product.get("nutriscore_grade", "N/A").upper()

                return {
                    "source": "OpenFoodFacts 🌐",
                    "barcode": barcode,
                    "product": product.get("product_name", "Unknown Product"),
                    "nutrition": nutrition,
                    "ecoscore": eco,
                    "ecoscoreColor": "green" if eco in ["A", "B"]
                                       else "orange" if eco == "C" else "red",
                    "nutriscore": nutri,
                    "nutriscoreColor": "green" if nutri in ["A", "B"]
                                        else "orange" if nutri == "C" else "red",
                    "healthLabel": label,
                    "healthLabelColor": color,
                    "tips": tips
                }
        except Exception as e:
            print("⚠️ OFF fetch error:", e)
    return None

# ------------------------------------------------------------
# 3️⃣ USDA last fallback
# ------------------------------------------------------------
def fetch_from_usda(barcode):
    try:
        url = f"https://api.nal.usda.gov/fdc/v1/foods/search?query={barcode}&api_key={USDA_API_KEY}"
        res = requests.get(url, timeout=6)
        data = res.json()
        if "foods" not in data or not data["foods"]:
            return None
        food = data["foods"][0]
        n = {x["nutrientName"]: x["value"] for x in food.get("foodNutrients", [])}
        nutrition = {
            "protein": f"{n.get('Protein', 0)} g",
            "carbs": f"{n.get('Carbohydrate, by difference', 0)} g",
            "fat": f"{n.get('Total lipid (fat)', 0)} g",
            "fiber": f"{n.get('Fiber, total dietary', 0)} g",
            "sugar": f"{n.get('Sugars, total including NLEA', 0)} g",
            "calories": f"{n.get('Energy', 0)} kcal"
        }
        label, color, tips = get_health_label_and_tips(nutrition)
        return {
            "source": "USDA FoodData Central 🇺🇸",
            "barcode": barcode,
            "product": food.get("description", "Unknown Product"),
            "nutrition": nutrition,
            "ecoscore": "N/A",
            "ecoscoreColor": "gray",
            "nutriscore": "N/A",
            "nutriscoreColor": "gray",
            "healthLabel": label,
            "healthLabelColor": color,
            "tips": tips
        }
    except Exception as e:
        print("⚠️ USDA fetch error:", e)
    return None

# ------------------------------------------------------------
# Main API Endpoint
# ------------------------------------------------------------
@app.route('/scan', methods=['POST'])
def scan_barcode():
    data = request.get_json(force=True)
    barcode = str(data.get("barcode", "")).strip()
    if not barcode:
        return jsonify({"error": "No barcode provided"}), 400
    if len(barcode) < 14:
        barcode = barcode.zfill(14)
    print(f"🔍 Scanning barcode: {barcode}")

    # 🔹 Priority: Local DB → OpenFoodFacts → USDA
    for fetcher in (fetch_from_local_db, fetch_from_openfoodfacts, fetch_from_usda):
        result = fetcher(barcode)
        if result:
            print(f"✅ Source: {result['source']}")
            return jsonify(result)

    return jsonify({
        "barcode": barcode,
        "product": "Unknown Product",
        "nutrition": {
            "protein": "0 g", "carbs": "0 g", "fat": "0 g",
            "fiber": "0 g", "sugar": "0 g", "calories": "0 kcal"
        },
        "ecoscore": "N/A", "ecoscoreColor": "gray",
        "nutriscore": "N/A", "nutriscoreColor": "gray",
        "healthLabel": "N/A", "healthLabelColor": "gray",
        "tips": ["No data found in Local DB, Open Food Facts, or USDA."]
    })

# ------------------------------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)

