
from flask import Flask, request, jsonify, send_from_directory, render_template_string
import os, json, traceback, base64, uuid
from dotenv import load_dotenv
from docx import Document
from docx.shared import Pt
from PIL import Image
import numpy as np
import openai
import easyocr

load_dotenv()

app = Flask(__name__, static_folder='static')

# Directorios
FILES_DIR, STATIC_DIR, UPLOADS_DIR = "generated_files", "static", "uploads"
os.makedirs(FILES_DIR, exist_ok=True)
os.makedirs(STATIC_DIR, exist_ok=True)
os.makedirs(UPLOADS_DIR, exist_ok=True)

# API Key y modelo
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise RuntimeError("❌ OPENAI_API_KEY no está configurada.")
client = openai.OpenAI(api_key=OPENAI_API_KEY)
MODEL = "gpt-4o"

# OCR
reader = easyocr.Reader(['es'], gpu=False)

# Contratos
with open("contratos.json", encoding="utf-8") as f:
    contratos_data = json.load(f)
PROMPTS = {k: v["prompt"] for k, v in contratos_data.items()}
NOMBRES = {k: v["nombre"] for k, v in contratos_data.items()}

@app.route("/")
def serve_index():
    try:
        with open(os.path.join(STATIC_DIR, "index.html"), encoding="utf-8") as f:
            return render_template_string(f.read())
    except FileNotFoundError:
        return "<h1>Index.html no encontrado</h1>", 404

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
        imagen = Image.open(archivo.stream).convert("RGB")
        texto = "\n".join(reader.readtext(np.array(imagen), detail=0, paragraph=True))
        return jsonify({"texto": texto})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": "Error en OCR"}), 500

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
