import os
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from bson import ObjectId
from typing import List, Optional
from datetime import datetime, timezone
from dotenv import load_dotenv # NOVO: Importa a função para carregar variáveis de ambiente

# NOVO: Carrega as variáveis de ambiente de um arquivo .env (ótimo para desenvolvimento local)
# Em produção (Render, Vercel), as variáveis serão injetadas diretamente pelo ambiente.
load_dotenv()

# --- Configuração da Aplicação FastAPI ---
app = FastAPI(
    title="API de Confirmação de Presença para Jantar",
    description="Uma API para registrar e listar confirmações de presença em um evento usando FastAPI e MongoDB.",
    version="1.0.0",
)

# --- Configuração do CORS ---
origins = [
    "https://jantar-muriloevictoria.vercel.app",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Conexão com o MongoDB Atlas (usando Variáveis de Ambiente) ---
# ALTERADO: A URL de conexão agora é lida de uma variável de ambiente por segurança.
MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = "jantar"
COLLECTION_NAME = "confirmacoes"

# NOVO: Adiciona uma verificação para garantir que a variável de ambiente foi carregada.
if not MONGO_URI:
    raise RuntimeError("A variável de ambiente MONGO_URI não foi definida. Crie um arquivo .env ou configure no seu provedor de hospedagem.")

try:
    client = MongoClient(MONGO_URI)
    client.admin.command('ping')
    db = client[DB_NAME]
    collection = db[COLLECTION_NAME]
    print("Conexão com o MongoDB Atlas estabelecida com sucesso!")
except ConnectionFailure as e:
    print(f"Não foi possível conectar ao MongoDB: {e}")
    collection = None
except Exception as e:
    print(f"Ocorreu um erro inesperado: {e}")
    collection = None

# --- Modelos de Dados (Pydantic) ---
# (Nenhuma alteração nesta seção)
class RSVPModel(BaseModel):
    nome: str = Field(..., min_length=2, description="Nome completo do convidado.")
    comparecera: bool = Field(..., description="Indica se o convidado irá comparecer.")
    tem_filhos: bool = Field(..., description="Indica se o convidado levará filhos.")
    nomes_dos_filhos: Optional[str] = Field(None, description="Nomes dos filhos, se houver.")
    restricao_alimentar: Optional[str] = Field(None, description="Qualquer restrição alimentar do convidado ou dos filhos.")

class RSVPResponse(RSVPModel):
    id: str = Field(alias="_id", description="ID único da confirmação.")
    timestamp: datetime = Field(..., description="Data e hora do registro da confirmação em formato ISO 8601.")

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_schema_extra = {
            "example": {
                "id": "60d5ec49f72e3e3b6c5a7e1a",
                "nome": "João da Silva",
                "comparecera": True,
                "tem_filhos": False,
                "nomes_dos_filhos": None,
                "restricao_alimentar": "Nenhuma",
                "timestamp": "2025-08-03T19:00:28.529Z"
            }
        }

# --- Funções Auxiliares ---
# (Nenhuma alteração nesta seção)
def convert_objectid_to_str(doc):
    if "_id" in doc and isinstance(doc["_id"], ObjectId):
        doc["_id"] = str(doc["_id"])
    return doc

# --- Endpoints da API ---
# (Nenhuma alteração nesta seção)
@app.post(
    "/rsvp",
    response_model=RSVPResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registra uma nova confirmação de presença",
    tags=["Confirmações"]
)
def registrar_presenca(rsvp: RSVPModel):
    if collection is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Não foi possível conectar ao banco de dados.",
        )
    rsvp_dict = rsvp.model_dump()
    rsvp_dict["timestamp"] = datetime.now(timezone.utc)
    result = collection.insert_one(rsvp_dict)
    created_rsvp = collection.find_one({"_id": result.inserted_id})
    if not created_rsvp:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Não foi possível criar e recuperar o registro de confirmação.",
        )
    return convert_objectid_to_str(created_rsvp)

@app.get(
    "/rsvp",
    response_model=List[RSVPResponse],
    summary="Lista todas as confirmações de presença",
    tags=["Confirmações"]
)
def listar_confirmacoes():
    if collection is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Não foi possível conectar ao banco de dados.",
        )
    confirmacoes = list(collection.find().sort("timestamp", -1))
    return [convert_objectid_to_str(c) for c in confirmacoes]

# --- Ponto de entrada para debug (opcional) ---
# (Nenhuma alteração nesta seção)
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)