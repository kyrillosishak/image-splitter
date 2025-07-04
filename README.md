# Image Splitter & Multimodal Analysis

A web application that allows users to upload images, select two points to create a split line, and analyze the relationship between the two image parts using a multimodal LLM.

## Architecture

The system consists of three main components:

1. **Frontend (React)** - User interface for image upload, point selection, and results display
2. **Local Backend (FastAPI)** - Image processing, splitting, and API coordination
3. **Remote vLLM Service (Kaggle/Colab)** - Multimodal LLM inference using SmolVLM2-500M-Video-Instruct

## Features

- **Robust Point Selection**: Precise click-to-select points on images with visual feedback
- **Intelligent Image Splitting**: Splits images along lines defined by two points
- **Multimodal Analysis**: Uses SmolVLM2 to analyze relationships between image parts
- **Fallback System**: Provides random responses when the remote LLM service is unavailable
- **Real-time Preview**: Shows split images and analysis results

## Setup Instructions

### Prerequisites

- Docker and Docker Compose
- (Optional) Kaggle account with GPU for remote LLM service
### 1. Kaggle/colab Setup (Optional)
If you want to run the vLLM service on Kaggle/Colab, follow these steps:

upload the provided Kaggle/colab notebook code to run the vLLM service

Or, Just run the following code in colab/kaggle notebook by:
1. copy&edit:  https://www.kaggle.com/code/kyrillosishak/ukp-application1 do not forget to switch to GPU runtime
2. Run this colab notebook: https://colab.research.google.com/drive/1ZLVP-Iz36kQgnjqRnA6B6cTTaw9YQaHx#scrollTo=EIFbKrgYFoG0
3. After running the notebook, you will get a URL from ngrok that you can use to connect your local application to the remote vLLM service, just copy the host link. You will find it something like this: ` * ngrok tunnel "https://331c-35-239-47-15.ngrok-free.app" -> "http://127.0.0.1:8081"
`. This is our URL : `https://331c-35-239-47-15.ngrok-free.app`
4. Make sure to set the environment variables in your local `.env` file as described below.

### 2. Local Setup
```bash
git clone image-splitter
cd image-splitter
```

### 2. Configure Environment Variables

Create a `.env` file in the root directory:
```bash
cp .env.example .env
```

Just replace `https://your-ngrok-url.ngrok.app` with the URL provided by ngrok when you run the vLLM service on Kaggle/Colab.
```env
# Remote vLLM service configuration
VLLM_HOST=https://your-ngrok-url.ngrok.app
VLLM_ENDPOINT=/api/v1/generate-response
```

### 3. Build and Run with Docker Compose

```bash
# Build and start all services
docker-compose up --build
```

### 4. Access the Application

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs

## Hyperparameters and Configuration

### vLLM Service (Kaggle)
- **Model**: `HuggingFaceTB/SmolVLM2-500M-Video-Instruct`
- **Data Type**: `half` (float16)
- **Max Model Length**: `8192` tokens
- **Tensor Parallel Size**: `1`
- **Multi-image Limit**: `2` images per prompt
- **Eager Mode**: `enabled` (for compatibility)

### Backend Configuration
- **Image Processing**: PIL (Pillow) for image splitting
- **Request Timeout**: 30 seconds for vLLM requests
- **Fallback Responses**: 10 predefined random responses
- **CORS**: Enabled for all origins (development mode)

## Usage

1. **Upload Image**: Click "Choose Image" and select an image file
2. **Select Points**: Click two points on the image to define the split line
3. **Enter Question**: Type a question about the relationship between the image parts
4. **Analyze**: Click "Analyze Images" to get the AI analysis
5. **View Results**: See the analysis result and split image previews

## API Endpoints

### Local Backend

- `POST /api/split-image` - Split image and analyze with LLM
- `GET /api/health` - Health check
- `GET /api/test-vllm` - Test vLLM connectivity

### Remote vLLM Service (Kaggle)

- `POST /api/v1/generate-response` - Generate response from multimodal LLM
- `POST /api/v1/generate-response-stream` - Streaming response (if needed)

## Development

### Running Locally Without Docker

#### Backend
```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

#### Frontend
```bash
cd frontend
npm install
npm start
```

### Environment Variables

- `VLLM_HOST`: URL of the remote vLLM service (default: http://localhost:8081)
- `VLLM_ENDPOINT`: API endpoint path (default: /api/v1/generate-response)
- `REACT_APP_BACKEND_URL`: Backend URL for frontend (default: http://localhost:8000)

## Kaggle Setup

Upload the provided Kaggle notebook code to run the vLLM service:

1. Create a new Kaggle notebook
2. Enable GPU acceleration
3. Copy the provided code
4. Run the cells to start vLLM and FastAPI services
5. Use the ngrok URL in your local environment configuration

## Error Handling

- **Connection Errors**: Automatic fallback to random responses
- **Image Processing Errors**: Detailed error messages
- **Invalid Input**: Client-side validation and error feedback
- **Service Unavailable**: Graceful degradation with mock responses

## Troubleshooting

### Common Issues

1. **Port Conflicts**: Ensure ports 3000 and 8000 are available
2. **vLLM Connection**: Check the ngrok URL and network connectivity
3. **Image Upload**: Verify image format support (PNG, JPEG, etc.)
4. **Docker Issues**: Ensure Docker daemon is running

### Logs

```bash
# View application logs
docker-compose logs -f

# View specific service logs
docker-compose logs -f backend
docker-compose logs -f frontend
```

## Technical Details

### Image Splitting Algorithm

The application uses a geometric approach to split images:

1. Convert user-selected points to pixel coordinates
2. Calculate the line equation: `ax + by + c = 0`
3. For each pixel, determine which side of the line it belongs to
4. Create two separate images with appropriate pixels

### Multimodal LLM Integration

- Uses OpenAI-compatible API format
- Sends both image parts as base64-encoded data
- Processes responses with error handling and fallbacks