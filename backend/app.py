from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import os
import base64
from dotenv import load_dotenv
import easyocr
from PIL import Image
import openai
import json
import numpy as np

load_dotenv()
app = Flask(__name__, static_url_path='', static_folder='.')
CORS(app)

openai.api_key = os.getenv("OPENAI_API_KEY")
reader = easyocr.Reader(['es'], gpu=False)

with open("contratos.json", encoding="utf-8") as f:
    contratos_data = json.load(f)

PROMPTS = {key: value["prompt"] for key, value in contratos_data.items()}
NOMBRES = {key: value["nombre"] for key, value in contratos_data.items()}


@app.route("/")
def index():
    return render_template("index.html")

@app.route("/auditoria.html")
def auditoria():
    return render_template("auditoria.html")

@app.route("/legal.html")
def legal():
    return render_template("legal.html")

@app.route("/politica.html")
def politica():
    return render_template("politica.html")

@app.route("/contratos", methods=["GET"])
def obtener_tipos():
    return jsonify(NOMBRES)

@app.route("/analizar", methods=["POST"])
def analizar():
    data = request.get_json()
    tipo = data.get("tipo")
    texto = data.get("texto")

    if not texto or tipo not in PROMPTS:
        return jsonify({"error": "Faltan datos válidos."}), 400

    prompt = f"{PROMPTS[tipo]}\n\nDocumento:\n{texto.strip()}"

    try:
        respuesta = openai.ChatCompletion.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "Actuás como un experto legal argentino."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.4,
        )
        output = respuesta.choices[0].message.content.strip()
        return jsonify({"respuesta": output})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/ocr", methods=["POST"])
def ocr():
    if 'archivo' not in request.files:
        return jsonify({"error": "No se recibió archivo"}), 400

    archivo = request.files['archivo']
    imagen = Image.open(archivo.stream).convert('RGB')
    resultado = reader.readtext(np.array(imagen), detail=0, paragraph=True)
    texto_extraido = "\n".join(resultado)
    return jsonify({"texto": texto_extraido})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5050))
    app.run(host="0.0.0.0", port=port)
