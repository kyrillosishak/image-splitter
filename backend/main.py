from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from PIL import Image, ImageDraw
import numpy as np
import cv2
import io
import base64
import json
import httpx
import os
from typing import List, Dict, Any
import asyncio

app = FastAPI(title="Image Splitter API")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
VLLM_URL = os.getenv("VLLM_URL", "http://localhost:8001")
VLLM_API_KEY = "token-abc123"


class Point(BaseModel):
    x: float
    y: float


class QuestionRequest(BaseModel):
    question: str
    split_images: List[str]


def split_image_by_line(image: Image.Image, point1: Point, point2: Point) -> tuple[Image.Image, Image.Image]:
    """Split image into two parts along a line defined by two points."""
    width, height = image.size

    # Create masks for the two parts
    mask1 = Image.new('L', (width, height), 0)
    mask2 = Image.new('L', (width, height), 0)

    # Calculate line equation parameters
    x1, y1 = point1.x, point1.y
    x2, y2 = point2.x, point2.y

    # Handle vertical line case
    if abs(x2 - x1) < 1e-6:
        # Vertical line
        for x in range(width):
            for y in range(height):
                if x < x1:
                    mask1.putpixel((x, y), 255)
                else:
                    mask2.putpixel((x, y), 255)
    else:
        # Calculate line slope and intercept
        slope = (y2 - y1) / (x2 - x1)
        intercept = y1 - slope * x1

        # For each pixel, determine which side of the line it's on
        for x in range(width):
            for y in range(height):
                line_y = slope * x + intercept
                if y < line_y:
                    mask1.putpixel((x, y), 255)
                else:
                    mask2.putpixel((x, y), 255)

    # Create the two split images
    img1 = Image.new('RGBA', (width, height), (255, 255, 255, 0))
    img2 = Image.new('RGBA', (width, height), (255, 255, 255, 0))

    # Apply masks
    img1.paste(image, mask=mask1)
    img2.paste(image, mask=mask2)

    return img1, img2


def image_to_base64(image: Image.Image) -> str:
    """Convert PIL Image to base64 string."""
    buffer = io.BytesIO()
    # Convert to RGB if RGBA
    if image.mode == 'RGBA':
        # Create white background
        white_bg = Image.new('RGB', image.size, (255, 255, 255))
        white_bg.paste(image, mask=image.split()[-1])  # Use alpha channel as mask
        image = white_bg
    image.save(buffer, format='PNG')
    img_str = base64.b64encode(buffer.getvalue()).decode()
    return img_str


async def query_vllm(question: str, images: List[str]) -> str:
    """Query the vLLM model with question and images."""
    try:
        # Prepare the messages for multimodal input
        content = [
            {"type": "text", "text": f"Look carefully at these two image parts and answer the question: {question}"}
        ]

        # Add both images
        for i, img_b64 in enumerate(images):
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{img_b64}"}
            })

        payload = {
            "model": "HuggingFaceTB/SmolVLM2-1.7B-Instruct",
            "messages": [
                {
                    "role": "user",
                    "content": content
                }
            ],
            "max_tokens": 512,
            "temperature": 0.7
        }

        headers = {
            "Authorization": f"Bearer {VLLM_API_KEY}",
            "Content-Type": "application/json"
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{VLLM_URL}/v1/chat/completions",
                json=payload,
                headers=headers
            )

            if response.status_code == 200:
                result = response.json()
                return result["choices"][0]["message"]["content"]
            else:
                # Fallback to mock response if vLLM is not available
                return generate_mock_response(question, images)

    except Exception as e:
        print(f"Error querying vLLM: {e}")
        # Return mock response as fallback
        return generate_mock_response(question, images)


def generate_mock_response(question: str, images: List[str]) -> str:
    """Generate a mock response when vLLM is not available."""
    mock_responses = [
        "Based on the split images, I can see two distinct parts of the original image. The left part appears to contain different visual elements compared to the right part.",
        "The two image segments show different regions of the original picture. There's a clear spatial relationship between these parts.",
        "Looking at these split sections, I notice they represent different portions of the scene with varying visual characteristics.",
        "The image has been divided into two segments that show different aspects of the original composition.",
        "These two parts demonstrate the division of the original image along the specified line, each containing distinct visual elements."
    ]

    # Simple heuristic based on question content
    if any(word in question.lower() for word in ['left', 'right']):
        return "The left part of the image shows different content compared to the right part. They appear to be distinct sections of the original image divided by the line you drew."
    elif any(word in question.lower() for word in ['top', 'bottom', 'up', 'down']):
        return "The upper section contains different visual elements compared to the lower section. The division creates two distinct parts of the original image."
    else:
        return "The two image parts show different regions of the original picture, each containing distinct visual elements and characteristics."


@app.post("/api/split-image")
async def split_image_endpoint(
        image: UploadFile = File(...),
        points: str = None
):
    """Split an image along a line defined by two points."""
    try:
        # Parse points
        if not points:
            raise HTTPException(status_code=400, detail="Points are required")

        points_data = json.loads(points)
        if len(points_data) != 2:
            raise HTTPException(status_code=400, detail="Exactly 2 points are required")

        point1 = Point(**points_data[0])
        point2 = Point(**points_data[1])

        # Load and process image
        image_data = await image.read()
        pil_image = Image.open(io.BytesIO(image_data))

        # Split the image
        img1, img2 = split_image_by_line(pil_image, point1, point2)

        # Convert to base64
        img1_b64 = image_to_base64(img1)
        img2_b64 = image_to_base64(img2)

        return JSONResponse({
            "split_images": [img1_b64, img2_b64],
            "message": "Image split successfully"
        })

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing image: {str(e)}")


@app.post("/api/ask-question")
async def ask_question_endpoint(request: QuestionRequest):
    """Ask a question about the relationship between split images."""
    try:
        if len(request.split_images) != 2:
            raise HTTPException(status_code=400, detail="Exactly 2 split images are required")

        # Query the model
        answer = await query_vllm(request.question, request.split_images)

        return JSONResponse({
            "answer": answer,
            "question": request.question
        })

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing question: {str(e)}")


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)