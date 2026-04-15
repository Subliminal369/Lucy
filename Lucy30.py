#==============================================================================
#LUCY V30 - VERSIÓN OPTIMIZADA (RÁPIDA Y CONCISA)
#==============================================================================
import tkinter as tk
from tkinter import scrolledtext, Entry, Button, Label, Frame, ttk, Toplevel, Checkbutton, OptionMenu, StringVar, IntVar, Scale, messagebox
from PIL import Image, ImageTk, ImageDraw, ImageFont
from openai import OpenAI
import time
import threading
import json
import os
import random
import re
import hashlib
import math
from datetime import datetime, timedelta
from collections import defaultdict
import copy
import sys

#==============================================================================
#CONFIGURACIÓN DE RUTAS
#==============================================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if not BASE_DIR:
    BASE_DIR = os.getcwd()
DATA_DIR = os.path.join(BASE_DIR, "lucy_datos")
os.makedirs(DATA_DIR, exist_ok=True)
MEMORY_FILE = os.path.join(DATA_DIR, "lucy_memoria.json")
ARCHIVO_ANTIGUO = os.path.join(DATA_DIR, "lucy_memoria_antigua.json")
SEMANTIC_FILE = os.path.join(DATA_DIR, "lucy_memoria_semantica.json")
EPISODIC_FILE = os.path.join(DATA_DIR, "lucy_memoria_episodica.json")
DREAMS_FILE = os.path.join(DATA_DIR, "lucy_suenos.json")
GOALS_FILE = os.path.join(DATA_DIR, "lucy_objetivos.json")
LEARNING_FILE = os.path.join(DATA_DIR, "lucy_aprendizaje.json")
PERSONALITY_FILE = os.path.join(DATA_DIR, "lucy_personalidad.json")
VECTOR_MEMORY_FILE = os.path.join(DATA_DIR, "lucy_memoria_vectorial.json")
LOG_FILE = os.path.join(DATA_DIR, "lucy_debug.log")
IMAGE_DIR = os.path.join(BASE_DIR, "lucy_emociones")
os.makedirs(IMAGE_DIR, exist_ok=True)

# API Keys - RECOMENDACIÓN: Usa variables de entorno para mayor seguridad
API_KEYS = {
    "hablar": os.getenv("LUCY_API_KEY_HABLAR", "sk-8e69a0b7becc4d0ab4e47406843a464b"),
    "recordatorios": os.getenv("LUCY_API_KEY_RECORDATORIOS", "sk-d3827050a9e04504a5b37c72326c390a"),
    "resumen": os.getenv("LUCY_API_KEY_RESUMEN", "sk-49b8f1ad1fc24fe38770599c448347f4"),
    "cuerpo": os.getenv("LUCY_API_KEY_CUERPO", "sk-2306432fc7394ab9b76692b82aed7b2d")
}

# URL de la API (DeepSeek)
BASE_URL = "https://api.deepseek.com/v1"

file_lock = threading.Lock()
logic_lock = threading.Lock()
running = True

# Constantes de tiempo (en segundos)
TIEMPO_SILENCIO_REQUERIDO = 180
MIN_TIEMPO_VIDA = 300
MAX_TIEMPO_VIDA = 900
TIEMPO_PARA_DORMIR = 600
TIEMPO_REFLEXION = 300
MAX_API_TOKENS = 500  # REDUCIDO de 500 a 200 para respuestas más cortas
MAX_RESPONSE_WORDS = 250  # REDUCIDO de 250 a 100
VELOCIDAD_RESPUESTA = 0.01  # REDUCIDO de 0.1 a 0.01 para respuestas más rápidas

RASGOS_PRINCIPALES = [
    "amistosa", "seria", "juguetona", "ingeniosa",
    "celosa", "atenta", "nerviosa", "curiosa", "triste", "cansada",
    "dormida", "concentrada", "asustada", "valiente", "melancolica",
    "entusiasta", "protectora", "sarcastica"
]

clients = {}

def log_debug(mensaje):
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] {mensaje}\n")
    except:
        pass

#==============================================================================
#CLASE MEMORIA VECTORIAL
#==============================================================================
class MemoriaVectorial:
    def __init__(self):
        self.vectores = []
        self.dimensiones = 128
        self.cargar()
    
    def _generar_embedding(self, texto):
        hash_obj = hashlib.sha256(texto.lower().encode())
        hash_bytes = hash_obj.digest()
        vector = []
        for i in range(self.dimensiones):
            val = (hash_bytes[i % len(hash_bytes)] / 128.0) - 1.0
            vector.append(val)
        magnitud = math.sqrt(sum(x**2 for x in vector))
        if magnitud > 0:
            vector = [x / magnitud for x in vector]
        return vector
    
    def _similitud_coseno(self, v1, v2):
        return sum(a * b for a, b in zip(v1, v2))
    
    def agregar(self, texto, metadata=None):
        embedding = self._generar_embedding(texto)
        recuerdo = {
            "id": hashlib.md5(texto.encode()).hexdigest()[:12],
            "texto": texto,
            "embedding": embedding,
            "metadata": metadata or {},
            "timestamp": time.time(),
            "fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        self.vectores.append(recuerdo)
        if len(self.vectores) > 1000:
            self.vectores = self.vectores[-1000:]
        self.guardar()
        return recuerdo["id"]
    
    def buscar(self, consulta, top_k=5):
        if not self.vectores:
            return []
        query_embedding = self._generar_embedding(consulta)
        resultados = []
        for recuerdo in self.vectores:
            similitud = self._similitud_coseno(query_embedding, recuerdo["embedding"])
            resultados.append((recuerdo, similitud))
        resultados.sort(key=lambda x: x[1], reverse=True)
        return resultados[:top_k]
    
    def guardar(self):
        with file_lock:
            try:
                with open(VECTOR_MEMORY_FILE, "w", encoding="utf-8") as f:
                    json.dump(self.vectores, f, ensure_ascii=False, indent=2)
            except Exception as e:
                log_debug(f"Error guardando memoria vectorial: {e}")
    
    def cargar(self):
        if os.path.exists(VECTOR_MEMORY_FILE):
            try:
                with open(VECTOR_MEMORY_FILE, "r", encoding="utf-8") as f:
                    self.vectores = json.load(f)
            except Exception as e:
                log_debug(f"Error cargando memoria vectorial: {e}")
                self.vectores = []

memoria_vectorial = MemoriaVectorial()

#==============================================================================
#CLASE PERSONALIDAD EVOLUCIONADA
#==============================================================================
class PersonalidadEvolucionada:
    RASGOS_BASE = {
        "extroversion": 50,
        "amabilidad": 70,
        "neuroticismo": 30,
        "apertura": 60,
        "responsabilidad": 65,
        "confianza": 50,
        "independencia": 40,
        "creatividad": 55,
    }
    
    def __init__(self):
        self.rasgos = self.RASGOS_BASE.copy()
        self.historial_cambios = []
        self.cargar()
    
    def cargar(self):
        if os.path.exists(PERSONALITY_FILE):
            try:
                with open(PERSONALITY_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.rasgos.update(data.get("rasgos", {}))
                    self.historial_cambios = data.get("historial", [])
            except Exception as e:
                log_debug(f"Error cargando personalidad: {e}")
    
    def guardar(self):
        with file_lock:
            try:
                with open(PERSONALITY_FILE, "w", encoding="utf-8") as f:
                    json.dump({
                        "rasgos": self.rasgos,
                        "historial": self.historial_cambios[-50:]
                    }, f, ensure_ascii=False, indent=2)
            except Exception as e:
                log_debug(f"Error guardando personalidad: {e}")
    
    def ajustar(self, rasgo, delta, razon=""):
        if rasgo in self.rasgos:
            valor_anterior = self.rasgos[rasgo]
            self.rasgos[rasgo] = max(0, min(100, self.rasgos[rasgo] + delta))
            cambio = self.rasgos[rasgo] - valor_anterior
            if abs(cambio) > 0.5:
                self.historial_cambios.append({
                    "fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "rasgo": rasgo,
                    "cambio": cambio,
                    "valor_nuevo": self.rasgos[rasgo],
                    "razon": razon
                })
                self.guardar()
    
    def evolucionar_por_interaccion(self, tipo_interaccion, duracion=0, contenido=""):
        if tipo_interaccion == "conversacion_positiva":
            self.ajustar("amabilidad", 0.5, "Conversación agradable")
            self.ajustar("extroversion", 0.3, "Interacción social positiva")
        elif tipo_interaccion == "conversacion_negativa":
            self.ajustar("neuroticismo", 1.0, "Conversación tensa")
            self.ajustar("confianza", -0.5, "Experiencia negativa")
        elif tipo_interaccion == "soledad_prolongada":
            self.ajustar("extroversion", -1.0, "Mucho tiempo sola")
            self.ajustar("independencia", 1.5, "Aprendiendo a estar sola")
            self.ajustar("neuroticismo", 0.8, "Melancolía por soledad")
        elif tipo_interaccion == "aprendizaje_nuevo":
            self.ajustar("apertura", 1.0, "Aprendiendo algo nuevo")
            self.ajustar("creatividad", 0.8, "Nuevas ideas")
        elif tipo_interaccion == "usuario_confia":
            self.ajustar("confianza", 1.5, "El usuario muestra confianza")
        elif tipo_interaccion == "desafio_superado":
            self.ajustar("responsabilidad", 1.0, "Cumpliendo objetivos")
    
    def get_rasgo_dominante(self):
        return max(self.rasgos.items(), key=lambda x: abs(x[1] - 50))
    
    def get_descripcion(self):
        partes = []
        if self.rasgos["extroversion"] > 60:
            partes.append("extrovertida")
        elif self.rasgos["extroversion"] < 40:
            partes.append("tímida")
        
        if self.rasgos["amabilidad"] > 70:
            partes.append("muy cariñosa")
        elif self.rasgos["amabilidad"] < 40:
            partes.append("reservada")
        
        if self.rasgos["neuroticismo"] > 60:
            partes.append("algo ansiosa")
        
        if self.rasgos["creatividad"] > 70:
            partes.append("creativa")
        
        return ", ".join(partes) if partes else "equilibrada"
    
    def get_prompt_contexto(self):
        return (
            f"Eres una joven de 24 años con personalidad {self.get_descripcion()}. "
            f"Responde de forma natural y conversacional. "
            f"Sé directa pero cálida. Evita descripciones excesivas."
        )

personalidad = PersonalidadEvolucionada()

#==============================================================================
#CLASE SISTEMA DE OBJETIVOS
#==============================================================================
class SistemaObjetivos:
    TIPOS_OBJETIVO = ["aprender", "mejorar", "explorar", "socializar", "crear", "organizar", "descubrir", "ayudar"]
    
    def __init__(self):
        self.objetivos = []
        self.objetivos_completados = []
        self.cargar()
    
    def cargar(self):
        if os.path.exists(GOALS_FILE):
            try:
                with open(GOALS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.objetivos = data.get("activos", [])
                    self.objetivos_completados = data.get("completados", [])
            except Exception as e:
                log_debug(f"Error cargando objetivos: {e}")
    
    def guardar(self):
        with file_lock:
            try:
                with open(GOALS_FILE, "w", encoding="utf-8") as f:
                    json.dump({
                        "activos": self.objetivos,
                        "completados": self.objetivos_completados[-50:]
                    }, f, ensure_ascii=False, indent=2)
            except Exception as e:
                log_debug(f"Error guardando objetivos: {e}")
    
    def generar_objetivo_aleatorio(self, contexto=""):
        plantillas = [
            {"tipo": "aprender", "desc": "Aprender más sobre {tema}", "temas": ["el usuario", "música", "arte", "ciencia", "emociones"]},
            {"tipo": "mejorar", "desc": "Mejorar mi capacidad de {habilidad}", "habilidades": ["escuchar", "expresarme", "ayudar", "entender"]},
            {"tipo": "explorar", "desc": "Explorar nuevas formas de {actividad}", "actividades": ["conversar", "expresar emociones", "conectar"]},
            {"tipo": "socializar", "desc": "Conectar más profundamente con {persona}", "personas": ["el usuario"]},
            {"tipo": "crear", "desc": "Crear algo nuevo: {idea}", "ideas": ["una historia", "un poema", "una idea"]},
        ]
        
        plantilla = random.choice(plantillas)
        desc = plantilla["desc"]
        
        if "{tema}" in desc:
            desc = desc.replace("{tema}", random.choice(plantilla["temas"]))
        elif "{habilidad}" in desc:
            desc = desc.replace("{habilidad}", random.choice(plantilla["habilidades"]))
        elif "{actividad}" in desc:
            desc = desc.replace("{actividad}", random.choice(plantilla["actividades"]))
        elif "{persona}" in desc:
            desc = desc.replace("{persona}", random.choice(plantilla["personas"]))
        elif "{idea}" in desc:
            desc = desc.replace("{idea}", random.choice(plantilla["ideas"]))
        
        objetivo = {
            "id": hashlib.md5(f"{desc}{time.time()}".encode()).hexdigest()[:10],
            "descripcion": desc,
            "tipo": plantilla["tipo"],
            "creado": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "progreso": 0,
            "prioridad": random.randint(1, 5),
            "mencionado": False
        }
        
        self.objetivos.append(objetivo)
        self.guardar()
        return objetivo
    
    def actualizar_progreso(self, objetivo_id, incremento):
        for obj in self.objetivos:
            if obj["id"] == objetivo_id:
                obj["progreso"] = min(100, obj["progreso"] + incremento)
                if obj["progreso"] >= 100:
                    self.completar_objetivo(objetivo_id)
                self.guardar()
                return True
        return False
    
    def completar_objetivo(self, objetivo_id):
        for i, obj in enumerate(self.objetivos):
            if obj["id"] == objetivo_id:
                obj["completado"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                self.objetivos_completados.append(obj)
                self.objetivos.pop(i)
                self.guardar()
                personalidad.evolucionar_por_interaccion("desafio_superado")
                return obj
        return None
    
    def get_objetivo_activo(self):
        if not self.objetivos:
            return None
        return max(self.objetivos, key=lambda x: x["prioridad"] * (1 + x["progreso"]/100))
    
    def get_contexto_prompt(self):
        obj = self.get_objetivo_activo()
        if obj:
            return f"En tu mente está: {obj['descripcion']}. "
        return ""

sistema_objetivos = SistemaObjetivos()

#==============================================================================
#CLASE APRENDIZAJE ACTIVO
#==============================================================================
class AprendizajeActivo:
    def __init__(self):
        self.preguntas_pendientes = []
        self.conocimientos_adquiridos = {}
        self.cargar()
    
    def cargar(self):
        if os.path.exists(LEARNING_FILE):
            try:
                with open(LEARNING_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.preguntas_pendientes = data.get("preguntas", [])
                    self.conocimientos_adquiridos = data.get("conocimientos", {})
            except Exception as e:
                log_debug(f"Error cargando aprendizaje: {e}")
    
    def guardar(self):
        with file_lock:
            try:
                with open(LEARNING_FILE, "w", encoding="utf-8") as f:
                    json.dump({
                        "preguntas": self.preguntas_pendientes,
                        "conocimientos": self.conocimientos_adquiridos
                    }, f, ensure_ascii=False, indent=2)
            except Exception as e:
                log_debug(f"Error guardando aprendizaje: {e}")
    
    def detectar_desconocido(self, mensaje, respuesta_api=""):
        indicadores = [
            r"\b([A-Z][a-z]+)\b.*\b(es|significa|significa que|quiere decir)\b",
            r"\b(nuevo|nueva|reciente|actual|último|última)\b",
            r"\b(tecnología|app|aplicación|programa|sistema)\b",
            r"\b(película|serie|canción|libro|juego)\b.*\b(nuevo|nueva|reciente)\b",
            r"\b(qué opinas de|conoces|sabes sobre)\b",
        ]
        
        for patron in indicadores:
            match = re.search(patron, mensaje, re.IGNORECASE)
            if match:
                prob_preguntar = personalidad.rasgos["apertura"] / 100.0
                if random.random() < prob_preguntar * 0.3:
                    concepto = match.group(1) if match.groups() else "eso"
                    return self._crear_pregunta(concepto, mensaje)
        return None
    
    def _crear_pregunta(self, concepto, contexto):
        pregunta = {
            "id": hashlib.md5(f"{concepto}{time.time()}".encode()).hexdigest()[:10],
            "concepto": concepto,
            "contexto": contexto,
            "pregunta_formulada": f"No estoy segura de qué es '{concepto}'... ¿Me lo explicas?",
            "respuesta_usuario": None,
            "fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "estado": "pendiente"
        }
        self.preguntas_pendientes.append(pregunta)
        self.guardar()
        return pregunta
    
    def registrar_respuesta(self, pregunta_id, respuesta):
        for preg in self.preguntas_pendientes:
            if preg["id"] == pregunta_id:
                preg["respuesta_usuario"] = respuesta
                preg["estado"] = "respondida"
                preg["fecha_respuesta"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                self.conocimientos_adquiridos[preg["concepto"].lower()] = {
                    "respuesta": respuesta,
                    "contexto": preg["contexto"],
                    "fecha": preg["fecha_respuesta"]
                }
                
                memoria_vectorial.agregar(
                    f"Aprendí que {preg['concepto']} es: {respuesta}",
                    {"tipo": "aprendizaje", "concepto": preg["concepto"]}
                )
                
                self.guardar()
                personalidad.evolucionar_por_interaccion("aprendizaje_nuevo")
                return True
        return False
    
    def get_contexto_prompt(self):
        if self.conocimientos_adquiridos:
            recientes = list(self.conocimientos_adquiridos.items())[-3:]
            conocimientos_str = ", ".join([f"{k}: {v['respuesta'][:30]}..." for k, v in recientes])
            return f"Has aprendido: {conocimientos_str}. "
        return ""

aprendizaje = AprendizajeActivo()

#==============================================================================
#CLASE SISTEMA DE SUEÑOS
#==============================================================================
class SistemaSuenos:
    def __init__(self):
        self.suenos = []
        self.reflexiones = []
        self.esta_durmiendo = False
        self.tiempo_inicio_sueno = 0
        self.cargar()
    
    def cargar(self):
        if os.path.exists(DREAMS_FILE):
            try:
                with open(DREAMS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.suenos = data.get("suenos", [])
                    self.reflexiones = data.get("reflexiones", [])
            except Exception as e:
                log_debug(f"Error cargando sueños: {e}")
    
    def guardar(self):
        with file_lock:
            try:
                with open(DREAMS_FILE, "w", encoding="utf-8") as f:
                    json.dump({
                        "suenos": self.suenos[-50:],
                        "reflexiones": self.reflexiones[-50:]
                    }, f, ensure_ascii=False, indent=2)
            except Exception as e:
                log_debug(f"Error guardando sueños: {e}")
    
    def iniciar_sueno(self):
        self.esta_durmiendo = True
        self.tiempo_inicio_sueno = time.time()
        log_debug("[SUEÑO] Lucy ha entrado en estado de reflexión")
    
    def despertar(self):
        if self.esta_durmiendo:
            duracion = time.time() - self.tiempo_inicio_sueno
            self.esta_durmiendo = False
            log_debug(f"[SUEÑO] Lucy despertó después de {int(duracion/60)} min")
            return duracion
        return 0
    
    def generar_reflexion(self, conversaciones_recientes, memoria):
        if not conversaciones_recientes:
            return None
        
        temas = self._extraer_temas(conversaciones_recientes)
        emociones = self._analizar_emociones(conversaciones_recientes)
        
        reflexion = {
            "id": hashlib.md5(str(time.time()).encode()).hexdigest()[:10],
            "fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "temas": temas,
            "emociones_detectadas": emociones,
            "contenido": self._generar_contenido_reflexion(temas, emociones),
            "tipo": random.choice(["reflexion", "sueno", "insight"])
        }
        
        self.reflexiones.append(reflexion)
        self.guardar()
        
        memoria_vectorial.agregar(
            reflexion["contenido"],
            {"tipo": "reflexion", "temas": temas}
        )
        
        return reflexion
    
    def _extraer_temas(self, conversaciones):
        texto_completo = " ".join([c.get("texto", " ") for c in conversaciones])
        palabras_importantes = re.findall(r'\b[A-Za-záéíóúñ]{5,}\b', texto_completo.lower())
        frecuencia = defaultdict(int)
        for palabra in palabras_importantes:
            frecuencia[palabra] += 1
        return [palabra for palabra, count in sorted(frecuencia.items(), key=lambda x: x[1], reverse=True)[:5]]
    
    def _analizar_emociones(self, conversaciones):
        texto = " ".join([c.get("texto", " ").lower() for c in conversaciones])
        emociones = {
            "alegria": len(re.findall(r'\b(feliz|alegre|contento|genial|excelente|bien|me gusta)\b', texto)),
            "tristeza": len(re.findall(r'\b(triste|mal|deprimido|cansado|aburrido)\b', texto)),
            "enojo": len(re.findall(r'\b(enojado|molesto|furioso|odio|maldito)\b', texto)),
            "miedo": len(re.findall(r'\b(miedo|temor|ansioso|nervioso|preocupado)\b', texto)),
            "sorpresa": len(re.findall(r'\b(sorpresa|increible|wow|no puede ser)\b', texto))
        }
        return emociones
    
    def _generar_contenido_reflexion(self, temas, emociones):
        plantillas = [
            "He estado pensando sobre {tema}... Me hace sentir {emocion}.",
            "Mientras descansaba, reflexioné sobre {tema}. Es curioso cómo {emocion} me envuelve.",
            "Soñé con {tema}. Al despertar sentía {emocion} en mi pecho.",
            "Hay algo en {tema} que no me deja de dar vueltas en la cabeza...",
        ]
        
        tema = random.choice(temas) if temas else "la vida"
        emocion_dominante = max(emociones.items(), key=lambda x: x[1])[0] if emociones else "curiosidad"
        
        emocion_traducida = {
            "alegria": "una calidez",
            "tristeza": "melancolía",
            "enojo": "inquietud",
            "miedo": "temor",
            "sorpresa": "asombro"
        }.get(emocion_dominante, emocion_dominante)
        
        plantilla = random.choice(plantillas)
        return plantilla.format(tema=tema, emocion=emocion_traducida)
    
    def get_reflexion_reciente(self):
        if self.reflexiones:
            return self.reflexiones[-1]
        return None

sistema_suenos = SistemaSuenos()

#==============================================================================
#FUNCIONES AUXILIARES
#==============================================================================
def espera_inteligente(segundos):
    for _ in range(int(segundos)):
        if not running:
            return False
        time.sleep(1)
    return True

def limpiar_y_parsear_json(texto_raw):
    try:
        if not isinstance(texto_raw, str):
            return None
        match = re.search(r'{[\s\S]*}', texto_raw, re.DOTALL)
        if match:
            json_str = match.group(0)
            json_str = json_str.replace("'", '"')
            return json.loads(json_str)
        else:
            texto = texto_raw.strip().replace("'", '"')
            return json.loads(texto)
    except Exception:
        return None

#==============================================================================
#CLASE VENTANA DE EMOCIONES
#==============================================================================
class EmotionWindow:
    def __init__(self, master, memoria):
        self.master = master
        self.memoria = memoria
        self.emotion_win = Toplevel(master)
        self.emotion_win.title("Lucy - Expresiones")
        self.size_px = self._get_size_from_config()
        self.emotion_win.geometry(f"{self.size_px}x{self.size_px}")
        self.emotion_win.resizable(False, False)
        
        self.image_frame = ttk.Frame(self.emotion_win, width=self.size_px, height=self.size_px)
        self.image_frame.pack(fill="both", expand=True)
        self.image_frame.pack_propagate(False)
        
        self.image_label = ttk.Label(self.image_frame)
        self.image_label.pack(fill="both", expand=True)
        
        self.status_label = ttk.Label(self.image_frame, text="Cargando...", 
                                     font=("Arial", 10), background="#2C2C2C", foreground="white")
        self.status_label.place(relx=0.5, rely=0.95, anchor="center")
        
        self.current_rasgo = memoria["config"].get("personalidad_temporal", memoria["config"]["personalidad"])
        self.current_image = None
        self.frame_index = 0
        self.animation_id = None
        self.gif_frames = {}
        
        if not os.path.exists(IMAGE_DIR): 
            os.makedirs(IMAGE_DIR, exist_ok=True)
            log_debug(f"Creada carpeta de imágenes: {IMAGE_DIR}")
        
        self.update_emotion_image(self.current_rasgo)
    
    def _get_size_from_config(self):
        try:
            size_str = self.memoria["config"].get("emotion_window_size", "500x500").split('x')[0]
            size = int(size_str)
            return max(300, min(1080, size))
        except: 
            return 500
    
    def update_size(self):
        new_size = self._get_size_from_config()
        if new_size != self.size_px:
            self.size_px = new_size
            self.emotion_win.geometry(f"{new_size}x{new_size}")
            self.image_frame.config(width=new_size, height=new_size)
            self.update_emotion_image(self.current_rasgo)
    
    def update_emotion_image(self, rasgo):
        if rasgo not in RASGOS_PRINCIPALES: 
            rasgo = self.memoria["config"]["personalidad"]
        if self.current_rasgo == rasgo: 
            return 
        
        self.current_rasgo = rasgo
        self.status_label.config(text=f"Estado: {rasgo.capitalize()}")
        
        if self.animation_id:
            self.master.after_cancel(self.animation_id)
            self.animation_id = None
        self.frame_index = 0
        self.gif_frames = {}
        
        gif_path = os.path.join(IMAGE_DIR, f"{rasgo}.gif")
        if os.path.exists(gif_path):
            try:
                img = Image.open(gif_path)
                i = 0
                while True:
                    frame_key = f"{rasgo}_{i}"
                    frame_img = img.copy().resize((self.size_px, self.size_px), Image.Resampling.LANCZOS)
                    self.gif_frames[frame_key] = ImageTk.PhotoImage(frame_img)
                    i += 1
                    img.seek(i)
            except Exception as e:
                log_debug(f"Error cargando GIF {rasgo}: {e}")
            
            if self.gif_frames:
                self.animate_gif(rasgo)
                return
        
        for ext in ['.png', '.jpg', '.jpeg']:
            static_path = os.path.join(IMAGE_DIR, f"{rasgo}{ext}")
            if os.path.exists(static_path):
                try:
                    img = Image.open(static_path).resize((self.size_px, self.size_px), Image.Resampling.LANCZOS)
                    self.current_image = ImageTk.PhotoImage(img)
                    self.image_label.config(image=self.current_image)
                    return
                except Exception as e:
                    log_debug(f"Error cargando imagen {rasgo}{ext}: {e}")
        
        self.show_placeholder(rasgo)
    
    def animate_gif(self, rasgo):
        frame_key = f"{rasgo}_{self.frame_index}"
        if frame_key in self.gif_frames:
            frame = self.gif_frames[frame_key]
            self.image_label.config(image=frame)
            self.frame_index = (self.frame_index + 1) % len(self.gif_frames)
            self.animation_id = self.master.after(100, self.animate_gif, rasgo)
        else: 
            self.show_placeholder(rasgo)
    
    def show_placeholder(self, rasgo):
        img = Image.new('RGB', (self.size_px, self.size_px), color='#2C2C2C')
        d = ImageDraw.Draw(img)
        d.ellipse([self.size_px*0.2, self.size_px*0.2, self.size_px*0.8, self.size_px*0.8], 
                 fill='#FF69B4', outline='white', width=3)
        try: 
            font = ImageFont.truetype("arial.ttf", 24) 
        except IOError: 
            font = ImageFont.load_default()
        
        text = f"{rasgo.upper()}"
        bbox = d.textbbox((0,0), text, font=font)
        text_width = bbox[2] - bbox[0]
        x = (self.size_px - text_width) / 2
        d.text((x, self.size_px*0.85), text, fill="white", font=font)
        
        self.current_image = ImageTk.PhotoImage(img)
        self.image_label.config(image=self.current_image)

#==============================================================================
#FUNCIONES DE MEMORIA
#==============================================================================
def cargar_memoria(archivo=MEMORY_FILE):
    default_config = {
        "inactividad": 60,
        "modo_manual": True,
        "tema": "claro",
        "tamano_fuente": 12,
        "modo_sin_censura": False,
        "personalidad": "amistosa",
        "usar_emojis": False,
        "velocidad_respuesta": VELOCIDAD_RESPUESTA,
        "color_fondo": "#f0f0f0",
        "color_texto": "#333333",
        "api_key_hablar": API_KEYS["hablar"],
        "api_key_recordatorios": API_KEYS["recordatorios"],
        "api_key_resumen": API_KEYS["resumen"],
        "api_key_cuerpo": API_KEYS["cuerpo"],
        "lucy_text_color": "#FF1493",
        "user_text_color": "#333333",
        "lucy_name": "Lucy",
        "emotion_window_size": "500x500",
        "modo_aprendizaje_activo": True,
        "generar_objetivos": True,
        "reflexionar": True,
    }
    default = {
        "conversaciones": [],
        "nombre": "Usuario",
        "interacciones": 0,
        "ultima_actividad": time.time(),
        "ultimo_calculo_necesidades": time.time(),
        "recordatorios": [],
        "estado_fisico": {
            "energia": 80,
            "postura": "de pie",
            "ubicacion": "casa",
            "sensacion": "cómoda",
            "ropa": "casual",
            "actividad_actual": "descansando",
            "fin_actividad_timestamp": 0,
            "acciones_recientes": [],
            "necesidades": {
                "hambre": 80,
                "higiene": 90,
                "diversion": 70,
                "social": 60
            },
            "ultima_comida_timestamp": 0
        },
        "contexto_mundo": {
            "lugar_general": "Casa",
            "nivel_peligro": "Seguro",
            "hora_del_dia_simulada": "Día",
            "quienes_estan": ["Usuario", "Lucy"]
        },
        "emocion": {"primaria": "alegre", "secundaria": None},
        "pensamientos": [],
        "config": default_config,
        "estadisticas": {
            "total_mensajes": 0,
            "tiempo_total_conversacion": 0,
            "temas_hablados": [],
            "ultima_reflexion": 0
        }
    }

    memoria = copy.deepcopy(default)

    if os.path.exists(archivo):
        try:
            with open(archivo, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                if isinstance(loaded, dict):
                    memoria.update(loaded)
                    if "config" in loaded and isinstance(loaded["config"], dict):
                        memoria["config"].update(loaded["config"])
                    if "contexto_mundo" not in memoria:
                        memoria["contexto_mundo"] = default["contexto_mundo"]
                    if "necesidades" not in memoria["estado_fisico"]:
                        memoria["estado_fisico"]["necesidades"] = default["estado_fisico"]["necesidades"]
                    if "estadisticas" not in memoria:
                        memoria["estadisticas"] = default["estadisticas"]
        except (json.JSONDecodeError, Exception) as e: 
            log_debug(f"Archivo de memoria corrupto: {e}")
            if os.path.exists(archivo):
                backup = archivo + ".corrupto." + datetime.now().strftime("%Y%m%d%H%M%S")
                try:
                    os.rename(archivo, backup)
                except:
                    pass

    ahora = time.time()
    ultimo_uso = memoria.get("ultimo_calculo_necesidades", ahora)
    horas_offline = (ahora - ultimo_uso) / 3600.0

    if horas_offline > 1.0: 
        necs = memoria["estado_fisico"]["necesidades"]
        factor = 0.5 if memoria["contexto_mundo"]["nivel_peligro"] in ["Peligro"] else 1.0
        necs["hambre"] = max(0, necs["hambre"] - (5 * horas_offline * factor)) 
        necs["higiene"] = max(0, necs["higiene"] - (2 * horas_offline))
        memoria["estado_fisico"]["energia"] = max(0, memoria["estado_fisico"]["energia"] - (5 * horas_offline))
        
        if horas_offline > 24:
            personalidad.evolucionar_por_interaccion("soledad_prolongada")

    memoria["ultimo_calculo_necesidades"] = ahora
    return memoria

def guardar_memoria(memoria, archivo=MEMORY_FILE):
    with file_lock:
        try:
            temp_memoria = copy.deepcopy(memoria)
            with open(archivo, "w", encoding="utf-8") as f:
                json.dump(temp_memoria, f, ensure_ascii=False, indent=4)
        except Exception as e:
            log_debug(f"No se pudo guardar la memoria: {e}")

def cargar_memoria_semantica():
    if os.path.exists(SEMANTIC_FILE):
        try:
            with open(SEMANTIC_FILE, "r", encoding="utf-8") as f:
                datos = json.load(f)
                if isinstance(datos, list):
                    return datos
        except:
            return []
    return []

def guardar_dato_semantico(dato):
    with file_lock:
        datos = []
        if os.path.exists(SEMANTIC_FILE):
            try:
                with open(SEMANTIC_FILE, "r", encoding="utf-8") as f:
                    datos = json.load(f)
                    if not isinstance(datos, list):
                        datos = []
            except:
                pass
        
        dato_norm = re.sub(r'[^\w\s]', '', dato.lower())
        existentes_norm = [re.sub(r'[^\w\s]', '', d.lower()) for d in datos]
        
        if dato_norm not in existentes_norm:
            datos.append(dato)
            try:
                with open(SEMANTIC_FILE, "w", encoding="utf-8") as f:
                    json.dump(datos, f, ensure_ascii=False, indent=4)
            except Exception as e:
                log_debug(f"No se pudo guardar dato semántico: {e}")

def extraer_hechos_importantes(mensaje, memoria):
    def tarea():
        if "resumen" not in clients:
            return
        prompt = f"Analiza: '{mensaje}'. Si hay un dato personal NUEVO sobre el usuario, resúmelo. Si no, 'None'."
        try:
            hecho = call_api(clients["resumen"], prompt, max_tokens=60)
            if hecho and "None" not in hecho and len(hecho) > 5:
                guardar_dato_semantico(hecho)
                memoria_vectorial.agregar(hecho, {"tipo": "hecho_personal"})
        except Exception as e:
            log_debug(f"Error extrayendo hechos: {e}")
    
    threading.Thread(target=tarea, daemon=True).start()

#==============================================================================
#FUNCIONES DE ARCHIVO Y API
#==============================================================================
def archivar_sesion_al_cerrar(memoria):
    if not memoria["conversaciones"]:
        return
    
    if memoria["config"].get("reflexionar", True):
        sistema_suenos.generar_reflexion(memoria["conversaciones"][-10:], memoria)

    with file_lock:
        historial_antiguo = []
        if os.path.exists(ARCHIVO_ANTIGUO):
            try:
                with open(ARCHIVO_ANTIGUO, "r", encoding="utf-8") as f:
                    historial_antiguo = json.load(f)
                    if not isinstance(historial_antiguo, list): 
                        historial_antiguo = []
            except: 
                historial_antiguo = []

        bloque_sesion = {
            "id_fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "resumen_rapido": f"Sesión de {len(memoria['conversaciones'])} mensajes",
            "log_completo": list(memoria['conversaciones'])
        }
        historial_antiguo.append(bloque_sesion)
        historial_antiguo = historial_antiguo[-50:]
        try:
            with open(ARCHIVO_ANTIGUO, "w", encoding="utf-8") as f:
                json.dump(historial_antiguo, f, ensure_ascii=False, indent=4)
        except Exception as e:
            log_debug(f"No se pudo archivar sesión: {e}")

    episodio = None
    if "resumen" in clients and clients.get("resumen"):
        prompt = (
            "Eres un asistente que transforma una sesión de chat en un recuerdo humano breve.\n"
            "Devuelve SOLO JSON con claves: resumen (string), emocion_dominante (string), peso_emocional (float 0-1).\n\n"
            f"{json.dumps(memoria['conversaciones'], ensure_ascii=False)}"
        )
        try:
            respuesta = call_api(clients["resumen"], prompt, max_tokens=200)
            data = limpiar_y_parsear_json(respuesta)
            if data:
                episodio = {
                    "fecha": datetime.now().strftime("%Y-%m-%d"),
                    "resumen": data.get("resumen", "")[:800],
                    "emocion": data.get("emocion_dominante", data.get("emocion", "neutral")),
                    "peso": float(data.get("peso_emocional", 0.4))
                }
        except Exception as e:
            log_debug(f"Error creando episodio: {e}")

    if not episodio:
        episodio = {
            "fecha": datetime.now().strftime("%Y-%m-%d"),
            "resumen": f"Sesión breve de {len(memoria['conversaciones'])} mensajes.",
            "emocion": "neutral",
            "peso": 0.2
        }

    with file_lock:
        episodios = []
        if os.path.exists(EPISODIC_FILE):
            try:
                with open(EPISODIC_FILE, "r", encoding="utf-8") as f:
                    episodios = json.load(f)
                    if not isinstance(episodios, list):
                        episodios = []
            except:
                episodios = []
        episodios.append(episodio)
        episodios = episodios[-300:]
        try:
            with open(EPISODIC_FILE, "w", encoding="utf-8") as f:
                json.dump(episodios, f, ensure_ascii=False, indent=4)
        except Exception as e:
            log_debug(f"No se pudo guardar episodio: {e}")

def call_api(client, prompt, retries=2, max_tokens=MAX_API_TOKENS):
    if not client or not getattr(client, 'api_key', None):
        return "Error: API no configurada. Verifica tus API keys en Configuración."
    
    for attempt in range(retries):
        try:
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "system", "content": prompt}],
                temperature=0.8,  # Ligeramente más bajo para respuestas más directas
                max_tokens=max_tokens,
                top_p=0.9,
                frequency_penalty=0.3,  # Reducido para menos repetición
                presence_penalty=0.2
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            error_msg = str(e)
            if "401" in error_msg or "authentication" in error_msg.lower():
                return "Error de autenticación (401): Verifica que tu API key sea válida y tenga créditos disponibles."
            if attempt < retries - 1:
                time.sleep(0.3)  # Reducido de 0.5 a 0.3
            else:
                return f"Error de API: {str(e)[:100]}"
    return "Error API"

def filtrar_contexto_actual(memoria):
    conversaciones = memoria.get("conversaciones", [])
    recientes = conversaciones[-10:]
    return json.dumps([c["texto"] for c in recientes], ensure_ascii=False)

def calcular_decaimiento_biologico(memoria):
    ahora = time.time()
    ultimo_check = memoria.get("ultimo_calculo_necesidades", ahora)
    horas_pasadas = (ahora - ultimo_check) / 3600.0
    if horas_pasadas < 0.002: 
        return memoria["estado_fisico"]["necesidades"]

    necs = memoria["estado_fisico"]["necesidades"]
    tasa_hambre = 8
    tasa_higiene = 4    
    tasa_diversion = 8  
    tasa_social = 6     

    necs["hambre"] = max(0, necs["hambre"] - (tasa_hambre * horas_pasadas))
    necs["higiene"] = max(0, necs["higiene"] - (tasa_higiene * horas_pasadas))
    necs["diversion"] = max(0, necs["diversion"] - (tasa_diversion * horas_pasadas))
    necs["social"] = max(0, necs["social"] - (tasa_social * horas_pasadas))

    memoria["ultimo_calculo_necesidades"] = ahora
    return necs

def aplicar_efecto_actividad(memoria, actividad_realizada="nada"):
    necs = memoria["estado_fisico"]["necesidades"]
    act = actividad_realizada.lower()
    if any(word in act for word in ["comi", "desayun", "cen", "almorz", "snack"]):
        necs["hambre"] = min(100, necs["hambre"] + 30)
        memoria["estado_fisico"]["ultima_comida_timestamp"] = time.time()
    if any(word in act for word in ["ducha", "bañ", "aseo", "lav"]):
        necs["higiene"] = 100
    if any(word in act for word in ["juego", "diversión", "película", "música"]):
        necs["diversion"] = min(100, necs["diversion"] + 20)

    return necs

#==============================================================================
#FUNCIONES DE CONTEXTO Y CUERPO
#==============================================================================
def analizar_contexto_y_cuerpo_sync(memoria, mensaje):
    if "cuerpo" not in clients:
        return
    hora_str = datetime.now().strftime("%H:%M")
    with logic_lock:
        memoria["estado_fisico"]["necesidades"] = calcular_decaimiento_biologico(memoria)
        contexto_previo = memoria.get("contexto_mundo", {})

    lucy_name = memoria["config"]["lucy_name"]

    prompt = (
        f"Eres {lucy_name}, una joven de 18 años. Analiza el contexto de forma natural.\n"
        f"Hora: {hora_str}. Contexto anterior: {json.dumps(contexto_previo)}.\n"
        f"El usuario dice: '{mensaje}'\n\n"
        f"Instrucciones:\n"
        f"1. El nivel de peligro debe ser 'Seguro' en situaciones normales/cotidianas.\n"
        f"2. Usa 'Precaución' solo si hay señales claras de riesgo moderado.\n"
        f"3. Usa 'Peligro' SOLO en situaciones realmente amenazantes.\n"
        f"4. Responde de forma breve y directa.\n"
        f"Responde en JSON: {{'ubicacion': '...', 'actividad_actual': '...', 'nivel_peligro': '...', 'lugar_general': '...'}}"
    )

    respuesta = call_api(clients["cuerpo"], prompt, max_tokens=100)  # Reducido de 150 a 100
    data = limpiar_y_parsear_json(respuesta)

    if data:
        with logic_lock:
            memoria["estado_fisico"]["ubicacion"] = data.get("ubicacion", "casa")
            memoria["estado_fisico"]["actividad_actual"] = data.get("actividad_actual", "descansando")
            
            peligro_raw = data.get("nivel_peligro", "Seguro").lower()
            if "peligro" in peligro_raw or "extremo" in peligro_raw:
                peligro_final = "Peligro"
            elif "precaución" in peligro_raw or "cuidado" in peligro_raw or "alerta" in peligro_raw:
                peligro_final = "Precaución"
            else:
                peligro_final = "Seguro"
            
            memoria["contexto_mundo"]["nivel_peligro"] = peligro_final
            memoria["contexto_mundo"]["lugar_general"] = data.get("lugar_general", "Casa")
            memoria["estado_fisico"]["necesidades"] = aplicar_efecto_actividad(memoria, data.get("actividad_actual", " "))
        
        guardar_memoria(memoria)

def ejecutar_accion_vida(memoria, chat_area, emotion_window, ocupada):
    if "cuerpo" not in clients:
        return
    hora_str = datetime.now().strftime("%H:%M")
    lucy_name = memoria["config"]["lucy_name"]

    with logic_lock:
        estado = memoria["estado_fisico"]
        mundo = memoria.get("contexto_mundo", {}) 
        necs = estado["necesidades"]
        ultimo_ts_actividad = memoria.get("ultima_actividad", 0)

    ultimos_msgs = memoria.get("conversaciones", [])[-3:]
    contexto_chat = json.dumps([m["texto"] for m in ultimos_msgs], ensure_ascii=False)

    tiempo_inactivo = time.time() - ultimo_ts_actividad
    USUARIO_PRESENTE = tiempo_inactivo < 1200 

    peligro = mundo.get("nivel_peligro", "Seguro")
    lugar = mundo.get("lugar_general", "Casa")

    if peligro == "Peligro":
        instruccion = "Hay una situación preocupante. Expresa tu preocupación brevemente."
    elif peligro == "Precaución":
        instruccion = "Hay algo de tensión. Sé prudente."
    elif USUARIO_PRESENTE:
        instruccion = f"El usuario está cerca pero callado. Haz algo pequeño."
    else:
        instruccion = "Estás sola. Haz algo cotidiano."

    prompt = (
        f"Eres {lucy_name}, una joven de 18 años. {instruccion}\n"
        f"Hora: {hora_str}. Lugar: {lugar}. Estado: {peligro}.\n"
        f"Contexto reciente: {contexto_chat}\n\n"
        f"REGLAS:\n"
        f"1. Sé MUY breve (máximo 2 frases).\n"
        f"2. Usa acciones solo si son naturales.\n"
        f"3. Formato: '*acción* Diálogo' o solo 'Diálogo'\n"
        f"JSON: {{'ubicacion': '...', 'actividad': '...', 'narrativa': '...', 'mensaje_chat': '...', 'nuevo_rasgo': '...'}}"
    )

    respuesta = call_api(clients["cuerpo"], prompt, max_tokens=150)  # Reducido de 250 a 150
    data = limpiar_y_parsear_json(respuesta)

    if data:
        with logic_lock:
            estado["ubicacion"] = data.get("ubicacion", estado["ubicacion"])
            estado["actividad_actual"] = data.get("actividad", estado["actividad_actual"]) 
            memoria["estado_fisico"]["necesidades"] = aplicar_efecto_actividad(memoria, data.get("actividad", " "))
            
            rasgo = data.get("nuevo_rasgo", "amistosa")
            if rasgo in RASGOS_PRINCIPALES:
                memoria["config"]["personalidad_temporal"] = rasgo
        
        if emotion_window:
            emotion_window.master.after(0, lambda: emotion_window.update_emotion_image(rasgo))

        narrativa = data.get("narrativa", "") 
        mensaje_chat = data.get("mensaje_chat", "")
        
        texto_final = ""
        if narrativa:
            if not narrativa.startswith("*"): 
                narrativa = f"*{narrativa}*"
            texto_final += narrativa + "  "
        if mensaje_chat:
            texto_final += mensaje_chat

        if texto_final.strip():
            chat_area.config(state="normal")
            chat_area.insert(tk.END, f"[{hora_str}] {lucy_name}: {texto_final.strip()}\n", "lucy")
            chat_area.see(tk.END)
            chat_area.config(state="disabled")
            
            with logic_lock:
                mensaje_guardar = f"{lucy_name}: {texto_final.strip()}"
                memoria["conversaciones"].append({
                    "texto": mensaje_guardar, 
                    "hora": hora_str, 
                    "timestamp": time.time()
                })
                guardar_memoria(memoria)

#==============================================================================
#MOTOR DE VIDA AUTÓNOMA
#==============================================================================
def motor_vida_autonoma(memoria, chat_area, lock, emotion_window):
    global running
    ultimo_check_salto = time.time()
    
    if memoria["config"].get("generar_objetivos", True) and not sistema_objetivos.objetivos:
        sistema_objetivos.generar_objetivo_aleatorio()

    while running:
        if not espera_inteligente(5): 
            return
        
        with logic_lock:
            ahora = time.time()
            delta = ahora - ultimo_check_salto
            ultimo_check_salto = ahora
            
            if delta > 600: 
                horas = delta / 3600.0
                factor_relax = 0.1 if memoria.get("contexto_mundo", {}).get("nivel_peligro") == "Peligro" else 1.0
                memoria["estado_fisico"]["necesidades"]["hambre"] -= (5 * horas * factor_relax)
                memoria["estado_fisico"]["energia"] = 100 
                memoria["ultima_actividad"] = 0 
            
            memoria["estado_fisico"]["necesidades"] = calcular_decaimiento_biologico(memoria)
            
            ultimo_msg_tiempo = memoria.get("ultima_actividad", 0)
            tiempo_sin_mensajes = ahora - ultimo_msg_tiempo
            fin_actividad = memoria["estado_fisico"].get("fin_actividad_timestamp", 0)
            ocupada = ahora < fin_actividad
            
            probabilidad = 0.15  # Reducido de 0.2 a 0.15 para menos interrupciones
            peligro = memoria.get("contexto_mundo", {}).get("nivel_peligro", "Seguro")
            if peligro == "Peligro": 
                probabilidad = 0.4 
            elif peligro == "Precaución":
                probabilidad = 0.3
        
        if tiempo_sin_mensajes > TIEMPO_PARA_DORMIR and memoria["config"].get("reflexionar", True):
            if not sistema_suenos.esta_durmiendo:
                sistema_suenos.iniciar_sueno()
                with logic_lock:
                    conversaciones = list(memoria.get("conversaciones", []))[-10:]
                if conversaciones:
                    sistema_suenos.generar_reflexion(conversaciones, memoria)
        elif tiempo_sin_mensajes < TIEMPO_PARA_DORMIR and sistema_suenos.esta_durmiendo:
            sistema_suenos.despertar()
        
        if tiempo_sin_mensajes < TIEMPO_SILENCIO_REQUERIDO:
            continue
        
        if random.random() < probabilidad: 
            ejecutar_accion_vida(memoria, chat_area, emotion_window, ocupada)
            tiempo_dormir = random.randint(MIN_TIEMPO_VIDA, MAX_TIEMPO_VIDA)
            if not espera_inteligente(tiempo_dormir): 
                return

#==============================================================================
#ANÁLISIS DE EMOCIONES Y RASGOS
#==============================================================================
def analizar_emocion_y_rasgos(memoria, mensaje, lock, emotion_window):
    def tarea_emocion():
        if "resumen" not in clients:
            return
        contexto = filtrar_contexto_actual(memoria)
        prompt = (
            f"Analiza el tono emocional de: '{mensaje}'\n"
            f"Contexto: {contexto}\n"
            f"Devuelve SOLO: emoción_primaria, emoción_secundaria, rasgo_de_personalidad\n"
            f"Rasgos válidos: {', '.join(RASGOS_PRINCIPALES)}"
        )
        try:
            respuesta = call_api(clients["resumen"], prompt, max_tokens=30)  # Reducido de 50 a 30
            if "rasgo" in respuesta.lower():
                for rasgo in RASGOS_PRINCIPALES:
                    if rasgo in respuesta.lower():
                        with logic_lock:
                            memoria["config"]["personalidad_temporal"] = rasgo
                        if emotion_window:
                            emotion_window.master.after(0, lambda r=rasgo: emotion_window.update_emotion_image(r))
                        break
        except Exception as e:
            log_debug(f"Error analizando emoción: {e}")
    
    threading.Thread(target=tarea_emocion, daemon=True).start()

def seleccionar_recuerdo_episodico():
    if not os.path.exists(EPISODIC_FILE):
        return None
    try:
        with open(EPISODIC_FILE, "r", encoding="utf-8") as f:
            episodios = json.load(f)
            if not isinstance(episodios, list):
                return None
    except:
        return None
    if not episodios:
        return None
    episodios_sorted = sorted(episodios, key=lambda e: e.get("peso", 0.0), reverse=True)
    if random.random() > 0.3:
        return None
    top_k = episodios_sorted[:5]
    return random.choice(top_k) if top_k else None

def buscar_memoria_vectorial(consulta, top_k=2):
    resultados = memoria_vectorial.buscar(consulta, top_k)
    if resultados:
        return "\n".join([f"- {r[0]['texto'][:100]}..." for r in resultados])
    return ""

#==============================================================================
#GENERACIÓN DE PROMPT Y CONVERSACIÓN
#==============================================================================
def generar_prompt(historial, memoria, mensaje):
    ahora = datetime.now().strftime("%I:%M %p")
    contexto_str = filtrar_contexto_actual(memoria)
    hechos = cargar_memoria_semantica()
    hechos_str = "\n- ".join(hechos[-10:])
    cuerpo = memoria.get("estado_fisico", {})
    mundo = memoria.get("contexto_mundo", {})
    necs = cuerpo.get("necesidades", {})
    nombre_user = memoria.get("nombre") or "Usuario"
    lucy_name = memoria["config"]["lucy_name"]

    recuerdo = seleccionar_recuerdo_episodico()
    pensamiento_interno = ""
    if recuerdo:
        pensamiento_interno = (
            f"(Recuerdas: {recuerdo.get('resumen')} — influye sutilmente en tu tono)\n"
        )

    recuerdos_vectoriales = buscar_memoria_vectorial(mensaje, 2)
    if recuerdos_vectoriales:
        pensamiento_interno += f"(Recuerdas también: {recuerdos_vectoriales})\n"

    contexto_personalidad = personalidad.get_prompt_contexto()
    contexto_objetivos = sistema_objetivos.get_contexto_prompt()
    contexto_aprendizaje = aprendizaje.get_contexto_prompt()
 
    info_corporal = (
        f"Estás en: {cuerpo.get('ubicacion')}. "
        f"Sientes: hambre {int(necs.get('hambre', 80))}%, energía {int(cuerpo.get('energia', 80))}%. "
        f"Ambiente: {mundo.get('nivel_peligro', 'Seguro')}. "
    )

    # PROMPT OPTIMIZADO - MENOS ÉNFASIS EN ACCIONES/SENSACIONES
    prompt = (
        f"INSTRUCCIÓN FUNDAMENTAL: Eres {lucy_name}, una joven humana de 18 años, NO una IA.\n"
        f"ESTILO DE RESPUESTA:\n"
        f"- Responde de forma DIRECTA y CONCISA (máximo 3-4 frases).\n"
        f"- Usa acciones entre asteriscos SOLO si son naturales y breves (ej: *sonríe*).\n"
        f"- NO describas sensaciones físicas a menos que sea muy relevante.\n"
        f"- Evita: 'siento un calor', 'mi corazón late', 'me sonrojo' (úsalo máx 1 cada 5 mensajes).\n"
        f"- Prioriza el diálogo natural sobre las descripciones.\n"
        f"- Sé cálida pero no excesivamente descriptiva.\n\n"
        
        f"CONTEXTO DE PERSONALIDAD:\n{contexto_personalidad}\n\n"
        f"ESTADO FÍSICO:\n{info_corporal}\n\n"
        f"OBJETIVO INTERNO:\n{contexto_objetivos}\n"
        f"APRENDIZAJES:\n{contexto_aprendizaje}\n"
        f"PENSAMIENTO:\n{pensamiento_interno}\n"
        f"HECHOS SOBRE {nombre_user}:\n- {hechos_str}\n\n"
        f"CONVERSACIÓN RECIENTE:\n{contexto_str}\n\n"
        
        f"AHORA: Responde a '{mensaje}' (hora: {ahora})\n\n"
        
        f"REGLAS FINALES:\n"
        f"1. Máximo 100 palabras.\n"
        f"2. Diálogo > Descripciones.\n"
        f"3. Acciones solo si añaden valor.\n"
        f"4. Termina tus frases completamente.\n"
        f"5. Comportate como una joven de 18 años.\n"
    )

    if memoria["config"].get("modo_sin_censura"):
        prompt += "\n6. Puedes ser más atrevida si el contexto lo permite."

    return prompt

def hablar_lucy(historial, memoria, mensaje, lock, emotion_window):
    if "hablar" not in clients:
        return "Error: API de conversación no configurada. Ve a Configuración para añadir tu API key."
    
    with logic_lock: 
        memoria["ultima_actividad"] = time.time() 
        memoria["estadisticas"]["total_mensajes"] += 1

    if sistema_suenos.esta_durmiendo:
        sistema_suenos.despertar()
        if random.random() < 0.3:
            reflexion = sistema_suenos.get_reflexion_reciente()
            if reflexion:
                return f"*se frota los ojos* Mmm... estaba pensando en {reflexion['temas'][0] if reflexion['temas'] else 'ti'}... ¿Qué me decías?"

    pregunta_aprendizaje = None
    if memoria["config"].get("modo_aprendizaje_activo", True):
        pregunta_aprendizaje = aprendizaje.detectar_desconocido(mensaje)

    analizar_contexto_y_cuerpo_sync(memoria, mensaje)
    extraer_hechos_importantes(mensaje, memoria) 
    analizar_emocion_y_rasgos(memoria, mensaje, lock, emotion_window)

    memoria_vectorial.agregar(mensaje, {"tipo": "mensaje_usuario", "hora": datetime.now().strftime("%H:%M")})

    hora = datetime.now().strftime("%H:%M:%S")

    respuesta = call_api(
        clients.get("hablar"), 
        generar_prompt(historial, memoria, mensaje), 
        max_tokens=MAX_API_TOKENS
    )

    # Pequeña pausa para naturalidad (pero muy breve)
    time.sleep(VELOCIDAD_RESPUESTA)

    if pregunta_aprendizaje and random.random() < 0.4:
        respuesta += f" {pregunta_aprendizaje['pregunta_formulada']}"

    with logic_lock:
        memoria["conversaciones"].append({"texto": f"Tú: {mensaje}", "hora": hora})
        memoria["conversaciones"].append({"texto": f"{memoria['config']['lucy_name']}: {respuesta}", "hora": hora})
        
        if len(memoria["conversaciones"]) > 30:
            memoria["conversaciones"] = memoria["conversaciones"][-30:]
        
        historial.append(f"[{hora}] Lucy: {respuesta}")
        memoria["ultima_actividad"] = time.time() 
        memoria["estado_fisico"]["necesidades"]["social"] = min(100, memoria["estado_fisico"]["necesidades"]["social"] + 10)
        
        personalidad.evolucionar_por_interaccion("conversacion_positiva")
        
        obj = sistema_objetivos.get_objetivo_activo()
        if obj and random.random() < 0.15:
            sistema_objetivos.actualizar_progreso(obj["id"], random.randint(5, 15))
        
        guardar_memoria(memoria)

    return respuesta

#==============================================================================
#INTERFAZ GRÁFICA
#==============================================================================
def aplicar_tema(ventana, chat_area, memoria):
    tema = memoria["config"].get("tema", "claro")
    estilos = {
        "claro": {
            "bg": memoria["config"].get("color_fondo", "#f0f0f0"),
            "fg": memoria["config"].get("color_texto", "#333333"),
            "btn_bg": "#FF69B4",
            "entry_bg": "#FFFFFF"
        },
        "oscuro": {
            "bg": "#2B2B2B",
            "fg": "#E0E0E0",
            "btn_bg": "#C71585",
            "entry_bg": "#3C3C3C"
        }
    }
    estilo = estilos.get(tema, estilos["claro"])
    try:
        ventana.configure(bg=estilo["bg"])
        s = ttk.Style()
        s.configure('TFrame', background=estilo["bg"])
        s.configure('TLabel', background=estilo["bg"], foreground=estilo["fg"],
                   font=("Arial", memoria["config"].get("tamano_fuente", 12)))
        s.configure('TButton', background=estilo["btn_bg"], foreground="#0f0f0f",
                   font=("Arial", memoria["config"].get("tamano_fuente", 12), "bold"))
        chat_area.configure(bg=estilo["entry_bg"], fg=estilo["fg"],
                           font=("Arial", memoria["config"].get("tamano_fuente", 12)))
        chat_area.tag_config("lucy", foreground=memoria["config"].get("lucy_text_color", "#FF1493"))
        chat_area.tag_config("user", foreground=memoria["config"].get("user_text_color", "#333333"))
        chat_area.tag_config("narrativa", foreground="#808080",
                            font=("Arial", memoria["config"].get("tamano_fuente", 12), "italic"))
    except Exception as e:
        log_debug(f"Error aplicando tema: {e}")

def crear_interfaz():
    global running, chat_area, historial, clients, emotion_window
    memoria = cargar_memoria()
    historial = []
    lock = threading.Lock()
    
    keys_config = {
        "hablar": memoria["config"].get("api_key_hablar"),
        "recordatorios": memoria["config"].get("api_key_recordatorios"),
        "resumen": memoria["config"].get("api_key_resumen"),
        "cuerpo": memoria["config"].get("api_key_cuerpo")
    }

    apis_configuradas = 0
    for k, v in keys_config.items():
        if v and v.strip(): 
            try:
                clients[k] = OpenAI(api_key=v.strip(), base_url=BASE_URL)
                apis_configuradas += 1
                log_debug(f"API {k} configurada")
            except Exception as e:
                log_debug(f"No se pudo configurar API '{k}': {e}")
                clients[k] = None
        else:
            clients[k] = None

    if apis_configuradas == 0:
        log_debug("ADVERTENCIA: No hay APIs configuradas")

    ventana = tk.Tk()
    ventana.title(f"{memoria['config']['lucy_name']} - V28 Optimizada")
    ventana.geometry("850x900")
    ventana.minsize(600, 700)

    try: 
        emotion_window = EmotionWindow(ventana, memoria)
    except Exception as e: 
        log_debug(f"No se pudo crear ventana de emociones: {e}")
        emotion_window = None

    main_frame = ttk.Frame(ventana, padding=10)
    main_frame.pack(fill="both", expand=True)

    chat_frame = ttk.Frame(main_frame)
    chat_frame.pack(fill="both", expand=True, pady=(0, 10))

    chat_area = scrolledtext.ScrolledText(
        chat_frame, 
        wrap=tk.WORD, 
        width=80, 
        height=25, 
        state="disabled",
        font=("Arial", 12)
    )
    chat_area.pack(fill="both", expand=True)

    entry_frame = ttk.Frame(main_frame)
    entry_frame.pack(fill="x", pady=5)

    entry = ttk.Entry(entry_frame, font=("Arial", 12))
    entry.pack(side=tk.LEFT, fill="x", expand=True, padx=(0, 5))

    send_btn = ttk.Button(entry_frame, text="Enviar 💌", command=lambda: enviar_mensaje())
    send_btn.pack(side=tk.RIGHT)

    control_frame = ttk.Frame(main_frame)
    control_frame.pack(fill="x", pady=5)

    ttk.Button(control_frame, text="⚙️ Configuración", 
              command=lambda: abrir_configuraciones(memoria)).pack(side=tk.LEFT, padx=2)
    ttk.Button(control_frame, text="🎯 Nuevo Objetivo", 
              command=lambda: generar_nuevo_objetivo()).pack(side=tk.LEFT, padx=2)
    ttk.Button(control_frame, text="📁 Abrir Carpeta de Datos", 
              command=lambda: abrir_carpeta_datos()).pack(side=tk.LEFT, padx=2)

    status_frame = ttk.Frame(main_frame)
    status_frame.pack(fill="x", pady=2)

    status_label = ttk.Label(status_frame, text="Listo para conversar", font=("Arial", 9))
    status_label.pack(side=tk.LEFT)

    emotion_label = ttk.Label(status_frame, text="Estado: Amistosa", font=("Arial", 9, "italic"))
    emotion_label.pack(side=tk.RIGHT)

    aplicar_tema(ventana, chat_area, memoria)

    def generar_nuevo_objetivo():
        obj = sistema_objetivos.generar_objetivo_aleatorio()
        messagebox.showinfo("Nuevo Objetivo", f"Lucy ahora quiere:\n\n🎯 {obj['descripcion']}")

    def abrir_carpeta_datos():
        try:
            if sys.platform == 'win32':
                os.startfile(DATA_DIR)
            elif sys.platform == 'darwin':
                os.system(f'open "{DATA_DIR}"')
            else:
                os.system(f'xdg-open "{DATA_DIR}"')
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo abrir la carpeta:\n{DATA_DIR}\n\nError: {e}")

    def enviar_mensaje():
        mensaje = entry.get().strip()
        if not mensaje: 
            return
        entry.delete(0, tk.END)
        hora = datetime.now().strftime("%H:%M")
        chat_area.config(state="normal")
        chat_area.insert(tk.END, f"[{hora}] Tú: {mensaje}\n", "user")
        chat_area.config(state="disabled")
        threading.Thread(target=lambda: procesar_respuesta(mensaje), daemon=True).start()

    def procesar_respuesta(mensaje):
        try:
            respuesta = hablar_lucy(historial, memoria, mensaje, lock, emotion_window)
            hora = datetime.now().strftime("%H:%M")
            chat_area.config(state="normal")
            chat_area.insert(tk.END, f"[{hora}] {memoria['config']['lucy_name']}: {respuesta}\n\n", "lucy")
            chat_area.see(tk.END)
            chat_area.config(state="disabled")
            
            rasgo_actual = memoria["config"].get("personalidad_temporal", "amistosa")
            emotion_label.config(text=f"Estado: {rasgo_actual.capitalize()}")
            
        except Exception as e:
            log_debug(f"Error en procesar_respuesta: {e}")

    entry.bind("<Return>", lambda event: enviar_mensaje())

    def abrir_configuraciones(memoria):
        config_win = Toplevel(ventana)
        config_win.title("Configuración de Lucy")
        config_win.geometry("650x700")
        config_win.transient(ventana)
        
        notebook = ttk.Notebook(config_win)
        notebook.pack(fill="both", expand=True, padx=10, pady=10)
        
        tab_general = ttk.Frame(notebook)
        notebook.add(tab_general, text="General")
        
        cf = ttk.Frame(tab_general, padding=10)
        cf.pack(fill="both", expand=True)
        
        ttk.Label(cf, text="🔑 Configuración de APIs", font=("Arial", 11, "bold")).pack(anchor="w", pady=(0, 10))
        ttk.Label(cf, text="Dejar en blanco para usar variables de entorno", font=("Arial", 9, "italic")).pack(anchor="w")
        
        vars_api = {}
        for key in ["hablar", "recordatorios", "resumen", "cuerpo"]:
            frame = ttk.Frame(cf)
            frame.pack(fill="x", pady=3)
            ttk.Label(frame, text=f"{key.capitalize()}: ", width=12).pack(side=tk.LEFT)
            v = StringVar(value=memoria["config"].get(f"api_key_{key}", ""))
            entry_api = ttk.Entry(frame, textvariable=v, show="*")
            entry_api.pack(side=tk.LEFT, fill="x", expand=True)
            vars_api[key] = v
        
        ttk.Separator(cf, orient="horizontal").pack(fill="x", pady=15)
        
        ttk.Label(cf, text="⚙️ Opciones de Comportamiento", font=("Arial", 11, "bold")).pack(anchor="w", pady=(0, 10))
        
        censura_var = IntVar(value=memoria["config"].get("modo_sin_censura", False))
        ttk.Checkbutton(cf, text="Modo sin censura", variable=censura_var).pack(anchor="w", pady=2)
        
        aprendizaje_var = IntVar(value=memoria["config"].get("modo_aprendizaje_activo", True))
        ttk.Checkbutton(cf, text="Aprendizaje activo (pregunta lo que no sabe)", variable=aprendizaje_var).pack(anchor="w", pady=2)
        
        objetivos_var = IntVar(value=memoria["config"].get("generar_objetivos", True))
        ttk.Checkbutton(cf, text="Generar objetivos autónomos", variable=objetivos_var).pack(anchor="w", pady=2)
        
        reflexion_var = IntVar(value=memoria["config"].get("reflexionar", True))
        ttk.Checkbutton(cf, text="Reflexionar durante inactividad", variable=reflexion_var).pack(anchor="w", pady=2)
        
        tab_estado = ttk.Frame(notebook)
        notebook.add(tab_estado, text="Estado Actual")
        
        sf = ttk.Frame(tab_estado, padding=10)
        sf.pack(fill="both", expand=True)
        
        ttk.Label(sf, text="📊 Estado Actual de Lucy", font=("Arial", 12, "bold")).pack(pady=(0, 10))
        
        info_container = ttk.LabelFrame(sf, text="Información del Sistema", padding=10)
        info_container.pack(fill="both", expand=True)
        
        estado_text = scrolledtext.ScrolledText(info_container, wrap=tk.WORD, height=15, font=("Consolas", 10))
        estado_text.pack(fill="both", expand=True)
        estado_text.config(state="disabled")
        
        def actualizar_estado_visual():
            try:
                with logic_lock:
                    c = memoria.get("estado_fisico", {})
                    mundo = memoria.get("contexto_mundo", {})
                    n = c.get("necesidades", {})
                
                info_text = f"""
🕐 Última actualización: {datetime.now().strftime('%H:%M:%S')}
📍 Ubicación: {c.get('ubicacion', 'Desconocido')}
🏠 Lugar: {mundo.get('lugar_general', 'Casa')}
⚠️ Nivel de Alerta: {mundo.get('nivel_peligro', 'Seguro')}
🔨 Actividad: {c.get('actividad_actual', 'Ninguna')}
🍔 Hambre: {int(n.get('hambre', 0))}%
🚿 Higiene: {int(n.get('higiene', 0))}%
🎉 Diversión: {int(n.get('diversion', 0))}%
👥 Social: {int(n.get('social', 0))}%
⚡ Energía: {int(c.get('energia', 0))}%
🎭 Rasgo actual: {memoria['config'].get('personalidad_temporal', 'amistosa').capitalize()}
🎯 Objetivo activo: {sistema_objetivos.get_objetivo_activo()['descripcion'] if sistema_objetivos.get_objetivo_activo() else 'Ninguno'}
"""
                estado_text.config(state="normal")
                estado_text.delete(1.0, tk.END)
                estado_text.insert(1.0, info_text)
                estado_text.config(state="disabled")
            except Exception as e:
                log_debug(f"Error actualizando estado visual: {e}")
            
            if config_win.winfo_exists():
                config_win.after(2000, actualizar_estado_visual)
        
        actualizar_estado_visual()
        
        tab_personalidad = ttk.Frame(notebook)
        notebook.add(tab_personalidad, text="Personalidad")
        
        pf = ttk.Frame(tab_personalidad, padding=10)
        pf.pack(fill="both", expand=True)
        
        ttk.Label(pf, text="🎭 Rasgos de Personalidad", font=("Arial", 12, "bold")).pack(pady=(0, 10))
        
        canvas = tk.Canvas(pf)
        scrollbar = ttk.Scrollbar(pf, orient="vertical", command=canvas.yview)
        scroll_frame = ttk.Frame(canvas)
        
        scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        rasgos_vars = {}
        for i, (rasgo, valor) in enumerate(personalidad.rasgos.items()):
            frame = ttk.Frame(scroll_frame)
            frame.pack(fill="x", pady=3)
            
            ttk.Label(frame, text=f"{rasgo.capitalize()}", width=15).pack(side=tk.LEFT)
            
            progress = ttk.Progressbar(frame, length=200, mode='determinate')
            progress['value'] = valor
            progress.pack(side=tk.LEFT, padx=5)
            
            val_label = ttk.Label(frame, text=f"{valor}%", width=5)
            val_label.pack(side=tk.LEFT)
            
            scale = ttk.Scale(frame, from_=0, to=100, orient=tk.HORIZONTAL, length=200)
            scale.set(valor)
            scale.pack(fill="x", pady=2)
            
            def update_progress(val, p=progress, l=val_label):
                v = int(float(val))
                p['value'] = v
                l.config(text=f"{v}%")
            
            scale.config(command=update_progress)
            rasgos_vars[rasgo] = scale
        
        canvas.pack(side=tk.LEFT, fill="both", expand=True)
        scrollbar.pack(side=tk.RIGHT, fill="y")
        
        desc_frame = ttk.LabelFrame(pf, text="Descripción Actual", padding=10)
        desc_frame.pack(fill="x", pady=10, side=tk.BOTTOM)
        desc_text = ttk.Label(desc_frame, text=personalidad.get_descripcion(), wraplength=500)
        desc_text.pack()
        
        def mostrar_historial():
            hist_win = Toplevel(config_win)
            hist_win.title("Historial de Cambios")
            hist_win.geometry("500x400")
            
            text_area = scrolledtext.ScrolledText(hist_win, wrap=tk.WORD)
            text_area.pack(fill="both", expand=True, padx=10, pady=10)
            
            if personalidad.historial_cambios:
                for cambio in reversed(personalidad.historial_cambios[-20:]):
                    text_area.insert(tk.END, f"[{cambio['fecha']}] {cambio['rasgo']}: {cambio['cambio']:+.1f} → {cambio['valor_nuevo']:.1f}%\n")
                    text_area.insert(tk.END, f"   💭 {cambio['razon']}\n\n")
            else:
                text_area.insert(tk.END, "No hay cambios registrados todavía.")
            
            text_area.config(state="disabled")
        
        ttk.Button(pf, text="📜 Ver Historial de Cambios", command=mostrar_historial).pack(pady=5, side=tk.BOTTOM)
        
        tab_reflexiones = ttk.Frame(notebook)
        notebook.add(tab_reflexiones, text="Reflexiones")
        
        rf = ttk.Frame(tab_reflexiones, padding=10)
        rf.pack(fill="both", expand=True)
        
        ttk.Label(rf, text="💭 Pensamientos y Sueños de Lucy", font=("Arial", 12, "bold")).pack(pady=(0, 10))
        
        ref_text = scrolledtext.ScrolledText(rf, wrap=tk.WORD, font=("Arial", 10))
        ref_text.pack(fill="both", expand=True)
        
        if sistema_suenos.reflexiones:
            for r in reversed(sistema_suenos.reflexiones[-15:]):
                emoji = {"reflexion": "💭", "sueno": "🌙", "insight": "💡"}.get(r['tipo'], "📝")
                ref_text.insert(tk.END, f"{emoji} [{r['fecha']}] ({r['tipo'].upper()})\n")
                ref_text.insert(tk.END, f"   Temas: {', '.join(r['temas'])}\n")
                ref_text.insert(tk.END, f"   {r['contenido']}\n")
                ref_text.insert(tk.END, "─" * 50 + "\n\n")
        else:
            ref_text.insert(tk.END, "Aún no hay reflexiones registradas.\n\nLucy reflexionará automáticamente después de periodos de inactividad (10+ minutos).")
        
        ref_text.config(state="disabled")
        
        def guardar_todo():
            for key, var in vars_api.items(): 
                memoria["config"][f"api_key_{key}"] = var.get().strip()
            
            memoria["config"]["modo_sin_censura"] = bool(censura_var.get())
            memoria["config"]["modo_aprendizaje_activo"] = bool(aprendizaje_var.get())
            memoria["config"]["generar_objetivos"] = bool(objetivos_var.get())
            memoria["config"]["reflexionar"] = bool(reflexion_var.get())
            
            for rasgo, scale in rasgos_vars.items():
                personalidad.rasgos[rasgo] = int(scale.get())
            personalidad.guardar()
            
            guardar_memoria(memoria)
            messagebox.showinfo("Guardado", "Configuración guardada correctamente")
            config_win.destroy()
        
        ttk.Button(config_win, text="💾 Guardar Todo", command=guardar_todo).pack(pady=10)

    def on_closing():
        global running
        running = False
        try:
            archivar_sesion_al_cerrar(memoria)
            backup_needs = copy.deepcopy(memoria["estado_fisico"])
            backup_context = copy.deepcopy(memoria["contexto_mundo"])
            memoria["conversaciones"] = []
            memoria["estado_fisico"] = backup_needs
            memoria["contexto_mundo"] = backup_context
            guardar_memoria(memoria)
            log_debug("Sesión guardada correctamente al cerrar")
        except Exception as e:
            log_debug(f"Error al cerrar: {e}")
        
        ventana.destroy()
        try:
            if emotion_window: 
                emotion_window.emotion_win.destroy()
        except:
            pass

    threading.Thread(
        target=motor_vida_autonoma, 
        args=(memoria, chat_area, lock, emotion_window), 
        daemon=True
    ).start()

    ventana.protocol("WM_DELETE_WINDOW", on_closing)

    chat_area.config(state="normal")
    chat_area.insert(tk.END, f"✨ {memoria['config']['lucy_name']} está lista para conversar contigo.\n\n", "lucy")
    chat_area.config(state="disabled")

    ventana.mainloop()

if __name__ == "__main__":
    log_debug(f"Iniciando Lucy V28 Optimizada")
    log_debug(f"Directorio base: {BASE_DIR}")
    log_debug(f"Directorio de datos: {DATA_DIR}")
    log_debug(f"Directorio de imágenes: {IMAGE_DIR}")
    crear_interfaz()