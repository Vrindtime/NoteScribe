from pydantic import BaseModel

class TextForm(BaseModel):
    text: str
    pace: str
    speed: float