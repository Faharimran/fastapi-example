import base64

from fastapi import FastAPI
from datetime import datetime, timezone
from fastapi.exceptions import HTTPException
from fastapi.requests import Request
from sqlmodel import SQLModel, create_engine , select, Field
from fastapi import Depends, Query
from sqlmodel import Session
from typing import Annotated, Generic, TypeVar, Optional 
from contextlib import asynccontextmanager
from fastapi.responses import Response
from pydantic import BaseModel
from annotated_types import T
from sqlalchemy import func
import json




class Campaign(SQLModel, table=True):
    campaign_id: int = Field(default = None, primary_key = True)
    name: str = Field(index=True)
    due_date: datetime | None = Field(default = None, index=True)
    created_at: datetime = Field(default_factory = lambda: datetime.now(timezone.utc), nullable=True, index=True)

class CampaignCreate(SQLModel):
    name: str
    due_date: datetime | None = None
    


sqlite_file_name = "database.db"
sqlite_url = f"sqlite:///{sqlite_file_name}"

connect_args = {"check_same_thread": False}
engine = create_engine(sqlite_url, connect_args = connect_args) 

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session

SessionDep = Annotated[Session, Depends(get_session)]

@asynccontextmanager
async def lifespan(app : FastAPI):
    create_db_and_tables()
    with Session(engine) as session:
        if not session.exec(select(Campaign)).first():
            session.add_all([
                Campaign(name="Summer Launch", due_date=datetime.now(timezone.utc)),
                Campaign(name="Black Friday", due_date=datetime.now(timezone.utc))
            ])
            session.commit()
    yield

T = TypeVar("T")
class Response(BaseModel, Generic[T]):
    data: T


app = FastAPI(root_path="/api/v1",lifespan=lifespan)

class PaginatedResponse(BaseModel,Generic[T]):
    data  : T
    next : Optional[str]
    # prev : Optional[str]
    # count : int
def encode_cursor(value):
    raw = json.dumps({'id': value})
    return base64.urlsafe_b64encode(raw.encode()).decode()
    
def decode_cursor(cursor):
    raw = base64.urlsafe_b64decode(cursor.encode()).decode()
    payload = json.loads(raw)
    return payload.get('id')


@app.get("/campaigns", response_model=PaginatedResponse[list[Campaign]])
async def read_campaigns(request: Request ,session: SessionDep, cursor : Optional[str] = Query(None), limit: int = Query(3, ge=1)):

    cursor_id = 0
    if cursor:
        cursor_id = decode_cursor(cursor)

    data = session.exec(select(Campaign).order_by(Campaign.campaign_id).where(Campaign.campaign_id > cursor_id).limit(limit+1)).all()
    base_url = str(request.url).split("?")[0]

    next_url = None 
    if len(data) > limit:
        next_cursor = encode_cursor(data[:limit][-1].campaign_id)
        next_url = f"{base_url}?cursor={next_cursor}&limit={limit}"
           
    return {
    
        "next": next_url,
       
        "data": data[:limit]
        }

@app.get("/campaigns/{id}", response_model=Response[Campaign])
async def read_campaign(id: int, session: SessionDep):
    data = session.get(Campaign, id)
    if not data:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return {"data": data}

@app.post("/campaigns", status_code= 201 ,response_model=Response[Campaign])
async def create_campaign(campaign : CampaignCreate, session: SessionDep):
    db_campaign = Campaign.model_validate(campaign)
    session.add(db_campaign)
    session.commit()
    session.refresh(db_campaign)
    return {"data": db_campaign}

@app.put("/campaigns/{id}", status_code= 200 ,response_model=Response[Campaign])
async def update_campaign(id: int, campaign : CampaignCreate, session: SessionDep):
    data = session.get(Campaign, id)
    if not data:
        raise HTTPException(status_code=404, detail="Campaign not found")
    data.name = campaign.name
    data.due_date = campaign.due_date
    session.add(data)
    session.commit()
    session.refresh(data)
    return {"data": data}

@app.delete("/campaigns/{id}", response_model=Response[Campaign])
async def delete_campaign(id: int, session: SessionDep):
    data = session.get(Campaign, id)
    if not data: 
        raise HTTPException(status_code=404, detail="Campaign not found")
    session.delete(data)
    session.commit()

# @app.post("/campaigns")
# async def create_campaign(body : dict[str, Any]):

#     new : Any = {
#     "campaign_id": randint(100,1000),
#      "name" : body.get("name"),
#      "due_date" : body.get("due_date"),
#      "created_at" : datetime.now()
#     }

#     data.append(new)
#     return {"campaign": new}


# @app.put("/campaigns/{id}")
# async def update_campaign(id: int, body : dict[str, Any]):
#     for index, campaign in enumerate(data):
#         if campaign.get("campaign_id") == id:
#             updated : Any = {
#             "campaign_id": id,
#             "name" : body.get("name"),
#             "due_date" : body.get("due_date"),
#             "created_at" : campaign.get("created_at")
#             }

#             data[index] = updated
#             return {"campaign" : updated}
#     raise HTTPException(status_code=404, detail="Campaign not found")


# @app.delete("/campaigns/{id}")
# async def update_campaign(id: int):
#     for index, campaign in enumerate(data):
#         if campaign.get("campaign_id") == id:
#             data.pop(index)
#             return Response(status_code=204)
#     raise HTTPException(status_code=404, detail="Campaign not found")
