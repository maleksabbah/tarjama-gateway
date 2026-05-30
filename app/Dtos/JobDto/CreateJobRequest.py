# app/Dtos/JobDto/Requests.py

from typing import Optional
from pydantic import BaseModel


class CreateJobRequest(BaseModel):
    file_path: str
    dialect: Optional[str] = "auto"
    output_type: Optional[str] = "all"
    subtitle_format: Optional[str] = "srt"
    burn_subtitles: Optional[bool] = False