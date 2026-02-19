import base64
import requests
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(
    prefix="/api/utils",
    tags=["utils"],
    responses={404: {"description": "Not found"}},
)

class S3UrlRequest(BaseModel):
    url: str

class Base64Response(BaseModel):
    base64_image: str
    content_type: str

@router.post("/s3-to-base64", response_model=Base64Response)
async def convert_s3_to_base64(request: S3UrlRequest):
    """
    Convert an S3 URL (including pre-signed URLs) to a base64 encoded string.
    """
    try:
        response = requests.get(request.url)
        response.raise_for_status()
        
        content_type = response.headers.get("Content-Type", "application/octet-stream")
        base64_encoded = base64.b64encode(response.content).decode("utf-8")
        
        return {
            "base64_image": base64_encoded,
            "content_type": content_type
        }
    except requests.RequestException as e:
        raise HTTPException(status_code=400, detail=f"Error fetching URL: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
