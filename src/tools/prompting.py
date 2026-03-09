from pydantic import BaseModel


class PromptTemplate(BaseModel):
    system:str
    user:str

