from flask import Flask, request, jsonify, send_from_directory, render_template_string
import os, json, traceback, base64, uuid
from dotenv import load_dotenv
from docx import Document
from docx.shared import Pt
from PIL import Image
import numpy as np
import openai
import requests

load_dotenv()

app = Flask(__name__, static_folder='static')

# Directorios
FILES_DIR, STATIC_DIR, UPLOADS_DIR = "generated_files", "static", "uploads"
os.makedirs(FILES_DIR, exist_ok=True)
os.makedirs(STATIC_DIR, exist_ok=True)
os.makedirs(UPLOADS_DIR, exist_ok=True)

# API Keys
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OCR_SPACE_API_KEY = os.getenv("OCR_SPACE_API_KEY")

if not OPENAI_API_KEY:
    raise RuntimeError("❌ OPENAI_API_KEY no está configurada.")

client = openai.OpenAI(api_key=OPENAI_API_KEY)
MODEL = "gpt-4o"

# Cargar prompts de contratos
with open("contratos.json", encoding="utf-8") as f:
    contratos_data = json.load(f)

PROMPTS = {k: v["prompt"] for k, v in contratos_data.items()}
NOMBRES = {k: v["nombre"] for k, v in contratos_data.items()}


@app.route("/")
def serve_index():
    return send_from_directory(STATIC_DIR, "index.html")


@app.route("/contratos", methods=["GET"])
def obtener_tipos():
    return jsonify(NOMBRES)


@app.route("/analizar", methods=["POST"])
def analizar():
    try:
        data = request.get_json()
        tipo = data.get("tipo")
        texto = data.get("texto", "").strip()

        if not texto or tipo not in PROMPTS:
            return jsonify({"error": "Faltan datos válidos."}), 400

        prompt = f"{PROMPTS[tipo]}\n\nDocumento:\n{texto}"

        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": "Actuás como un experto legal argentino."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.4
        )

        return jsonify({"respuesta": response.choices[0].message.content.strip()})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/ocr", methods=["POST"])
def ocr():
    try:
        archivo = request.files["archivo"]
        response = requests.post(
            "https://api.ocr.space/parse/image",
            files={"filename": (archivo.filename, archivo.stream)},
            data={
                "language": "spa",
                "apikey": OCR_SPACE_API_KEY,
                "isOverlayRequired": False
            }
        )

        # Verificación de tipo de respuesta
        try:
            resultado = response.json()
        except Exception:
            return jsonify({"error": "OCR falló (respuesta no válida de la API)."}), 500

        if not isinstance(resultado, dict):
            return jsonify({"error": "OCR falló (respuesta inesperada)."}), 500

        if resultado.get("IsErroredOnProcessing") or "ParsedResults" not in resultado:
            return jsonify({"error": "OCR falló"}), 500

        texto = resultado["ParsedResults"][0].get("ParsedText", "")
        return jsonify({"texto": texto})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": "Error en OCR externo"}), 500



@app.route("/descargar-pdf", methods=["POST"])
def descargar_pdf():
    try:
        from fpdf import FPDF
        data = request.get_json()
        texto = data.get("texto", "").strip()

        if not texto:
            return jsonify({"error": "Texto vacío"}), 400

        pdf = FPDF()
        pdf.add_page()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.set_font("Arial", size=12)
        for linea in texto.split("\n"):
            pdf.multi_cell(0, 10, linea)

        filename = f"analisis_{uuid.uuid4().hex}.pdf"
        filepath = os.path.join(FILES_DIR, filename)
        pdf.output(filepath)

        return send_from_directory(FILES_DIR, filename)
    except Exception:
        traceback.print_exc()
        return jsonify({"error": "No se pudo generar el PDF"}), 500


@app.route("/files/<filename>")
def download_file(filename):
    return send_from_directory(FILES_DIR, filename)


@app.route("/healthz")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
