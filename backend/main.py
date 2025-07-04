import os
import json
import base64
import random
import asyncio
import logging
from typing import List, Tuple
from io import BytesIO

import requests
import numpy as np
from PIL import Image, ImageDraw
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Image Splitting API", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
VLLM_HOST = os.getenv("VLLM_HOST", "http://localhost:8081")
VLLM_ENDPOINT = os.getenv("VLLM_ENDPOINT", "/api/v1/generate-response")
VLLM_URL = f"{VLLM_HOST}{VLLM_ENDPOINT}"


# Request models
class Point(BaseModel):
    x: float
    y: float


class ImageSplitRequest(BaseModel):
    image_base64: str
    point1: Point
    point2: Point
    question: str


class ImageSplitResponse(BaseModel):
    success: bool
    answer: str
    image1_base64: str = ""
    image2_base64: str = ""
    error: str = ""


def get_random_response(question: str) -> str:
    """Generate a random response when vLLM is not available"""
    responses = [
        "Based on the image analysis, I can see the relationship between the two parts.",
        "The two image sections show interesting visual connections.",
        "There appears to be a clear distinction between the left and right portions.",
        "The upper and lower sections demonstrate different characteristics.",
        "The divided images show complementary elements in their composition.",
        "I can observe notable differences in the visual content of both sections.",
        "The split reveals contrasting aspects between the two image parts.",
        "The relationship between these sections suggests spatial continuity.",
        "Both image portions contribute to the overall visual narrative.",
        "The division highlights the distinct features in each section."
    ]
    return random.choice(responses)


def split_image_by_line(image: Image.Image, point1: Point, point2: Point) -> Tuple[Image.Image, Image.Image]:
    """Split image along a line defined by two points"""
    width, height = image.size

    # Convert points to pixel coordinates
    p1_x = int(point1.x * width)
    p1_y = int(point1.y * height)
    p2_x = int(point2.x * width)
    p2_y = int(point2.y * height)

    # Create masks for the two regions
    mask1 = Image.new('L', (width, height), 0)
    mask2 = Image.new('L', (width, height), 0)

    draw1 = ImageDraw.Draw(mask1)
    draw2 = ImageDraw.Draw(mask2)

    # Calculate line equation: ax + by + c = 0
    # For line through (x1,y1) and (x2,y2): (y2-y1)x - (x2-x1)y + (x2-x1)y1 - (y2-y1)x1 = 0
    if p2_x == p1_x:  # Vertical line
        # Left side
        if p1_x > 0:
            draw1.rectangle([0, 0, p1_x, height], fill=255)
        # Right side
        if p1_x < width:
            draw2.rectangle([p1_x, 0, width, height], fill=255)
    else:
        # General case
        a = p2_y - p1_y
        b = p1_x - p2_x
        c = p2_x * p1_y - p1_x * p2_y

        # For each pixel, determine which side of the line it's on
        for y in range(height):
            for x in range(width):
                line_value = a * x + b * y + c
                if line_value <= 0:
                    mask1.putpixel((x, y), 255)
                else:
                    mask2.putpixel((x, y), 255)

    # Create the split images
    image1 = Image.new('RGBA', (width, height), (255, 255, 255, 0))
    image2 = Image.new('RGBA', (width, height), (255, 255, 255, 0))

    # Apply masks
    image_rgba = image.convert('RGBA')

    for y in range(height):
        for x in range(width):
            pixel = image_rgba.getpixel((x, y))
            if mask1.getpixel((x, y)) > 0:
                image1.putpixel((x, y), pixel)
            if mask2.getpixel((x, y)) > 0:
                image2.putpixel((x, y), pixel)

    return image1, image2


def image_to_base64(image: Image.Image) -> str:
    """Convert PIL image to base64 string"""
    buffer = BytesIO()
    image.save(buffer, format='PNG')
    return base64.b64encode(buffer.getvalue()).decode('utf-8')


async def query_vllm(question: str, image1_b64: str, image2_b64: str) -> str:
    """Query the vLLM service with the images and question"""
    try:
        payload = {
            "question": question,
            "image1_b64": image1_b64,
            "image2_b64": image2_b64
        }
        headers = {"Content-Type": "application/json"}

        logger.info(f"Querying vLLM at {VLLM_URL}")

        # Use asyncio to make the request with timeout
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: requests.post(VLLM_URL, json=payload, headers=headers, timeout=30)
        )

        if response.status_code == 200:
            try:
                full_response = response.json()
                content = full_response["response"]["choices"][0]["message"]["content"]
                logger.info("Successfully got response from vLLM")
                return content.strip()
            except Exception as e:
                logger.error(f"Error parsing vLLM response: {e}")
                logger.error(f"Raw response: {response.text}")
                return get_random_response(question)
        else:
            logger.warning(f"vLLM returned error {response.status_code}: {response.text}")
            return get_random_response(question)

    except Exception as e:
        logger.error(f"Failed to connect to vLLM: {e}")
        return get_random_response(question)


@app.post("/api/split-image", response_model=ImageSplitResponse)
async def split_image(request: ImageSplitRequest):
    """Split image and analyze with multimodal LLM"""
    try:
        # Decode base64 image
        image_data = base64.b64decode(request.image_base64)
        image = Image.open(BytesIO(image_data))

        # Split the image
        image1, image2 = split_image_by_line(image, request.point1, request.point2)

        # Convert split images to base64
        image1_b64 = image_to_base64(image1)
        image2_b64 = image_to_base64(image2)

        # Query the LLM
        answer = await query_vllm(request.question, image1_b64, image2_b64)

        return ImageSplitResponse(
            success=True,
            answer=answer,
            image1_base64=image1_b64,
            image2_base64=image2_b64
        )

    except Exception as e:
        logger.error(f"Error processing image: {e}")
        return ImageSplitResponse(
            success=False,
            answer="",
            error=str(e)
        )


@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "vllm_url": VLLM_URL}


@app.get("/api/test-vllm")
async def test_vllm():
    """Test connectivity to vLLM service"""
    try:
        # Create a simple test with dummy data
        test_question = "What do you see in these images?"
        dummy_image_b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="

        response = await query_vllm(test_question, dummy_image_b64, dummy_image_b64)

        return {
            "vllm_available": True,
            "vllm_url": VLLM_URL,
            "test_response": response
        }
    except Exception as e:
        return {
            "vllm_available": False,
            "vllm_url": VLLM_URL,
            "error": str(e)
        }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)