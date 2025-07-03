from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import os
import io
import base64
from PIL import Image, ImageDraw
import numpy as np
import requests
import json
from typing import List, Tuple
import threading
import time
import subprocess
import sys

app = FastAPI(title="Image Split Analyzer")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global variables for vLLM server management
vllm_process = None
vllm_ready = False


def start_vllm_server():
    """Start vLLM server in a separate process"""
    global vllm_process, vllm_ready

    model_name = os.getenv("MODEL_NAME", "HuggingFaceTB/SmolVLM2-1.7B-Instruct")

    try:
        # Start vLLM server
        cmd = [
            "python", "-m", "vllm.entrypoints.openai.api_server",
            "--model", model_name,
            "--port", "8001",
            "--host", "0.0.0.0",
            "--quantization", "awq",
            "--dtype", "auto",
            "--api-key", "token-abc123"
        ]

        vllm_process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        # Wait for server to be ready
        for _ in range(60):  # Wait up to 60 seconds
            try:
                response = requests.get("http://localhost:8001/health", timeout=2)
                if response.status_code == 200:
                    vllm_ready = True
                    print("vLLM server is ready!")
                    break
            except requests.RequestException:
                pass
            time.sleep(1)

        if not vllm_ready:
            print("vLLM server failed to start within timeout")

    except Exception as e:
        print(f"Error starting vLLM server: {e}")


def split_image_by_line(image: Image.Image, point1: Tuple[int, int], point2: Tuple[int, int]) -> Tuple[
    Image.Image, Image.Image]:
    """Split image into two parts along a line defined by two points"""
    width, height = image.size

    # Create masks for the two parts
    mask1 = Image.new('L', (width, height), 0)
    mask2 = Image.new('L', (width, height), 0)

    draw1 = ImageDraw.Draw(mask1)
    draw2 = ImageDraw.Draw(mask2)

    # Determine which side of the line each pixel is on
    x1, y1 = point1
    x2, y2 = point2

    # Create polygon for each half
    if x1 == x2:  # Vertical line
        if x1 < width // 2:
            # Left part
            draw1.rectangle([(0, 0), (x1, height)], fill=255)
            draw2.rectangle([(x1, 0), (width, height)], fill=255)
        else:
            # Right part
            draw1.rectangle([(x1, 0), (width, height)], fill=255)
            draw2.rectangle([(0, 0), (x1, height)], fill=255)
    else:
        # Calculate line equation: y = mx + b
        m = (y2 - y1) / (x2 - x1)
        b = y1 - m * x1

        # Create points for polygon division
        points1 = []
        points2 = []

        # Determine intersection points with image boundaries
        intersections = []

        # Check intersection with left edge (x=0)
        y_at_0 = b
        if 0 <= y_at_0 <= height:
            intersections.append((0, int(y_at_0)))

        # Check intersection with right edge (x=width)
        y_at_width = m * width + b
        if 0 <= y_at_width <= height:
            intersections.append((width, int(y_at_width)))

        # Check intersection with top edge (y=0)
        if m != 0:
            x_at_0 = -b / m
            if 0 <= x_at_0 <= width:
                intersections.append((int(x_at_0), 0))

        # Check intersection with bottom edge (y=height)
        if m != 0:
            x_at_height = (height - b) / m
            if 0 <= x_at_height <= width:
                intersections.append((int(x_at_height), height))

        # Remove duplicates and sort
        intersections = list(set(intersections))

        if len(intersections) >= 2:
            # Use the line to split the image
            # Determine which side is "upper" or "left"
            if y1 < y2:  # Line goes down
                # Upper part
                points1 = [(0, 0), (width, 0)] + intersections + [(0, 0)]
                points2 = intersections + [(width, height), (0, height)] + intersections[:1]
            else:  # Line goes up
                # Lower part
                points1 = intersections + [(0, height), (width, height)] + intersections[:1]
                points2 = [(0, 0), (width, 0)] + intersections + [(0, 0)]

            if len(points1) >= 3:
                draw1.polygon(points1, fill=255)
            if len(points2) >= 3:
                draw2.polygon(points2, fill=255)

    # Apply masks to create split images
    img1 = Image.new('RGBA', (width, height), (255, 255, 255, 0))
    img2 = Image.new('RGBA', (width, height), (255, 255, 255, 0))

    # Convert to RGBA if needed
    if image.mode != 'RGBA':
        image = image.convert('RGBA')

    # Apply masks
    for y in range(height):
        for x in range(width):
            pixel = image.getpixel((x, y))
            if mask1.getpixel((x, y)) > 0:
                img1.putpixel((x, y), pixel)
            if mask2.getpixel((x, y)) > 0:
                img2.putpixel((x, y), pixel)

    return img1, img2


def image_to_base64(image: Image.Image) -> str:
    """Convert PIL Image to base64 string"""
    buffered = io.BytesIO()
    image.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode()
    return img_str


def query_vllm(image1_b64: str, image2_b64: str, question: str) -> str:
    """Query the vLLM server with two images and a question"""
    global vllm_ready

    if not vllm_ready:
        # Return mock response if vLLM is not ready
        return f"Mock response: Based on the two image parts, I can see different sections of the image. Regarding your question '{question}', I would analyze the visual relationship between the left and right (or top and bottom) parts of the split image."

    try:
        # Prepare the request
        headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer token-abc123"
        }

        data = {
            "model": "HuggingFaceTB/SmolVLM2-1.7B-Instruct",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": f"I have split an image into two parts. Here are the two parts: First part and second part. Question: {question}"
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{image1_b64}"
                            }
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{image2_b64}"
                            }
                        }
                    ]
                }
            ],
            "max_tokens": 500,
            "temperature": 0.7
        }

        response = requests.post(
            "http://localhost:8001/v1/chat/completions",
            headers=headers,
            json=data,
            timeout=30
        )

        if response.status_code == 200:
            result = response.json()
            return result["choices"][0]["message"]["content"]
        else:
            return f"Error from vLLM: {response.status_code} - {response.text}"

    except Exception as e:
        return f"Mock response due to error: {str(e)}. Based on the two image parts, I can analyze the visual relationship between the sections. Regarding your question '{question}', I would examine the spatial and content relationships between the split parts."


@app.on_event("startup")
async def startup_event():
    """Start vLLM server when the app starts"""
    print("Starting vLLM server...")
    thread = threading.Thread(target=start_vllm_server)
    thread.daemon = True
    thread.start()


@app.on_event("shutdown")
async def shutdown_event():
    """Stop vLLM server when the app shuts down"""
    global vllm_process
    if vllm_process:
        vllm_process.terminate()
        vllm_process.wait()


@app.get("/health")
async def health_check():
    return {"status": "healthy", "vllm_ready": vllm_ready}


@app.post("/analyze")
async def analyze_image(
        image: UploadFile = File(...),
        point1_x: int = Form(...),
        point1_y: int = Form(...),
        point2_x: int = Form(...),
        point2_y: int = Form(...),
        question: str = Form(...)
):
    try:
        # Read and process the uploaded image
        contents = await image.read()
        pil_image = Image.open(io.BytesIO(contents))

        # Convert to RGB if needed
        if pil_image.mode in ('RGBA', 'LA'):
            # Create a white background
            background = Image.new('RGB', pil_image.size, (255, 255, 255))
            if pil_image.mode == 'RGBA':
                background.paste(pil_image, mask=pil_image.split()[-1])
            else:
                background.paste(pil_image, mask=pil_image.split()[-1])
            pil_image = background
        elif pil_image.mode != 'RGB':
            pil_image = pil_image.convert('RGB')

        # Split the image
        point1 = (point1_x, point1_y)
        point2 = (point2_x, point2_y)

        img1, img2 = split_image_by_line(pil_image, point1, point2)

        # Convert to base64
        img1_b64 = image_to_base64(img1)
        img2_b64 = image_to_base64(img2)

        # Query vLLM
        response = query_vllm(img1_b64, img2_b64, question)

        return JSONResponse({
            "success": True,
            "response": response,
            "image1": img1_b64,
            "image2": img2_b64,
            "vllm_ready": vllm_ready
        })

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)