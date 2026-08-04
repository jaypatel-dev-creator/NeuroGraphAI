from datetime import datetime
from pydantic import BaseModel

#get all 
class DocumentRead(BaseModel):
    sha256: str
    filename: str
    chunk_count: int
    uploaded_at: datetime

    model_config = {"from_attributes": True}


#post 
class DocumentUploadResponse(BaseModel):
    filename: str
    sha256: str
    chunk_count: int
    already_existed: bool
    message: str  # "indexed successfully — X chunks created" or "already indexed — ready to query"