import os
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from bson import ObjectId
from typing import List, Optional
from datetime import datetime, timezone

# --- Configuração da Aplicação FastAPI ---
app = FastAPI(
    title="API de Confirmação de Presença para Jantar",
    description="Uma API para registrar e listar confirmações de presença em um evento usando FastAPI e MongoDB.",
    version="1.0.0",
)

# --- Configuração do CORS ---
# Permite que o frontend (ex: React) acesse a API.
origins = [
    "http://localhost:8081",
    "http://localhost:8081",  # Exemplo de porta para um app React em desenvolvimento
    # Adicione aqui os domínios do seu frontend em produção.
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],  # Permite todos os métodos (GET, POST, etc.)
    allow_headers=["*"],  # Permite todos os cabeçalhos
)

# --- Conexão com o MongoDB Atlas ---
MONGO_URI = "mongodb+srv://murilosecundario14:YMN30KwXD8d9xsjn@clusterjantar.n02tubi.mongodb.net/?retryWrites=true&w=majority&appName=ClusterJantar"
DB_NAME = "jantar"
COLLECTION_NAME = "confirmacoes"

try:
    client = MongoClient(MONGO_URI)
    # A linha a seguir serve para verificar se a conexão foi bem-sucedida.
    client.admin.command('ping')
    db = client[DB_NAME]
    collection = db[COLLECTION_NAME]
    print("Conexão com o MongoDB Atlas estabelecida com sucesso!")
except ConnectionFailure as e:
    print(f"Não foi possível conectar ao MongoDB: {e}")
    # Em um app real, você poderia querer que a aplicação não iniciasse.
    # Para este exemplo, apenas imprimimos o erro.
    collection = None
except Exception as e:
    print(f"Ocorreu um erro inesperado: {e}")
    collection = None

# --- Modelos de Dados (Pydantic) ---

class RSVPModel(BaseModel):
    """
    Modelo de dados para o corpo da requisição de confirmação de presença.
    """
    nome: str = Field(..., min_length=2, description="Nome completo do convidado.")
    comparecera: bool = Field(..., description="Indica se o convidado irá comparecer.")
    tem_filhos: bool = Field(..., description="Indica se o convidado levará filhos.")
    nomes_dos_filhos: Optional[str] = Field(None, description="Nomes dos filhos, se houver.")
    restricao_alimentar: Optional[str] = Field(None, description="Qualquer restrição alimentar do convidado ou dos filhos.")

class RSVPResponse(RSVPModel):
    """
    Modelo de dados para a resposta da API, incluindo campos gerados pelo backend.
    """
    id: str = Field(alias="_id", description="ID único da confirmação.")
    timestamp: datetime = Field(..., description="Data e hora do registro da confirmação em formato ISO 8601.")

    class Config:
        # Permite que o Pydantic use 'alias' para mapear '_id' do MongoDB para 'id'.
        populate_by_name = True
        # Necessário para que o Pydantic consiga converter tipos complexos como ObjectId.
        arbitrary_types_allowed = True
        # Exemplo de como o modelo deve ser retornado no JSON.
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

def convert_objectid_to_str(doc):
    """Converte o ObjectId do MongoDB para uma string."""
    if "_id" in doc and isinstance(doc["_id"], ObjectId):
        doc["_id"] = str(doc["_id"])
    return doc

# --- Endpoints da API ---

@app.post(
    "/rsvp",
    response_model=RSVPResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registra uma nova confirmação de presença",
    tags=["Confirmações"]
)
def registrar_presenca(rsvp: RSVPModel):
    """
    Registra a confirmação de presença de um convidado no evento.

    - **nome**: Nome do convidado (obrigatório).
    - **comparecera**: Booleano indicando presença (obrigatório).
    - **tem_filhos**: Booleano indicando se levará filhos (obrigatório).
    - **nomes_dos_filhos**: String com os nomes dos filhos (opcional).
    - **restricao_alimentar**: String com as restrições alimentares (opcional).
    """
    if collection is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Não foi possível conectar ao banco de dados.",
        )

    # Converte o modelo Pydantic para um dicionário Python.
    rsvp_dict = rsvp.model_dump()

    # Adiciona o timestamp com a data e hora atuais em UTC.
    rsvp_dict["timestamp"] = datetime.now(timezone.utc)

    # Insere o novo documento na coleção.
    result = collection.insert_one(rsvp_dict)

    # Recupera o documento inserido para retornar na resposta.
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
    """
    Retorna uma lista com todas as confirmações de presença registradas,
    ordenadas da mais recente para a mais antiga.
    """
    if collection is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Não foi possível conectar ao banco de dados.",
        )

    # Busca todos os documentos na coleção, ordenando por 'timestamp' descendente.
    confirmacoes = list(collection.find().sort("timestamp", -1))

    # Converte o '_id' (ObjectId) de cada documento para string.
    return [convert_objectid_to_str(c) for c in confirmacoes]

# --- Ponto de entrada para debug (opcional) ---
if __name__ == "__main__":
    import uvicorn
    # Este bloco permite executar o script diretamente com `python main.py`
    # para fins de desenvolvimento.
    # Para produção, use: uvicorn main:app --host 0.0.0.0 --port 8000
    uvicorn.run(app, host="127.0.0.1", port=8000)