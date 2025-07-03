import React, { useState, useRef } from 'react';
import './App.css';

function App() {
  const [image, setImage] = useState(null);
  const [imageFile, setImageFile] = useState(null);
  const [points, setPoints] = useState([]);
  const [question, setQuestion] = useState('');
  const [response, setResponse] = useState('');
  const [splitImages, setSplitImages] = useState({ image1: null, image2: null });
  const [loading, setLoading] = useState(false);
  const [vllmReady, setVllmReady] = useState(false);
  const canvasRef = useRef(null);
  const imageRef = useRef(null);

  const handleImageUpload = (event) => {
    const file = event.target.files[0];
    if (file) {
      setImageFile(file);
      const reader = new FileReader();
      reader.onload = (e) => {
        setImage(e.target.result);
        setPoints([]);
        setResponse('');
        setSplitImages({ image1: null, image2: null });
      };
      reader.readAsDataURL(file);
    }
  };

  const handleCanvasClick = (event) => {
    if (points.length >= 2) return;

    const canvas = canvasRef.current;
    const rect = canvas.getBoundingClientRect();
    const x = event.clientX - rect.left;
    const y = event.clientY - rect.top;

    // Scale coordinates to match actual image size
    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;
    const actualX = Math.round(x * scaleX);
    const actualY = Math.round(y * scaleY);

    setPoints([...points, { x: actualX, y: actualY }]);
  };

  const drawImageAndPoints = () => {
    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    const img = imageRef.current;

    if (!img || !canvas) return;

    // Clear canvas
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Draw image
    ctx.drawImage(img, 0, 0, canvas.width, canvas.height);

    // Draw points
    ctx.fillStyle = 'red';
    ctx.strokeStyle = 'red';
    ctx.lineWidth = 2;

    points.forEach((point, index) => {
      const x = (point.x / img.naturalWidth) * canvas.width;
      const y = (point.y / img.naturalHeight) * canvas.height;

      // Draw point
      ctx.beginPath();
      ctx.arc(x, y, 5, 0, 2 * Math.PI);
      ctx.fill();

      // Draw point label
      ctx.fillText(`${index + 1}`, x + 10, y - 10);
    });

    // Draw line between points
    if (points.length === 2) {
      const x1 = (points[0].x / img.naturalWidth) * canvas.width;
      const y1 = (points[0].y / img.naturalHeight) * canvas.height;
      const x2 = (points[1].x / img.naturalWidth) * canvas.width;
      const y2 = (points[1].y / img.naturalHeight) * canvas.height;

      ctx.beginPath();
      ctx.moveTo(x1, y1);
      ctx.lineTo(x2, y2);
      ctx.stroke();
    }
  };

  const handleImageLoad = () => {
    const canvas = canvasRef.current;
    const img = imageRef.current;

    if (img && canvas) {
      // Set canvas size to match image aspect ratio
      const maxWidth = 600;
      const maxHeight = 400;

      let { width, height } = img;

      if (width > maxWidth) {
        height = (height * maxWidth) / width;
        width = maxWidth;
      }

      if (height > maxHeight) {
        width = (width * maxHeight) / height;
        height = maxHeight;
      }

      canvas.width = width;
      canvas.height = height;

      drawImageAndPoints();
    }
  };

  React.useEffect(() => {
    if (image) {
      drawImageAndPoints();
    }
  }, [points, image]);

  const handleAnalyze = async () => {
    if (!imageFile || points.length !== 2 || !question.trim()) {
      alert('Please upload an image, select two points, and enter a question.');
      return;
    }

    setLoading(true);
    setResponse('');

    try {
      const formData = new FormData();
      formData.append('image', imageFile);
      formData.append('point1_x', points[0].x);
      formData.append('point1_y', points[0].y);
      formData.append('point2_x', points[1].x);
      formData.append('point2_y', points[1].y);
      formData.append('question', question);

      const response = await fetch('/analyze', {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const result = await response.json();
      setResponse(result.response);
      setSplitImages({
        image1: result.image1,
        image2: result.image2
      });
      setVllmReady(result.vllm_ready);

    } catch (error) {
      console.error('Error:', error);
      setResponse(`Error: ${error.message}`);
    } finally {
      setLoading(false);
    }
  };

  const clearPoints = () => {
    setPoints([]);
    setResponse('');
    setSplitImages({ image1: null, image2: null });
  };

  return (
    <div className="App">
      <header className="App-header">
        <h1>Image Split Analyzer</h1>
        <p>Upload an image, select two points to split it, and ask a question about the relationship between the parts.</p>
      </header>

      <main className="App-main">
        <div className="upload-section">
          <input
            type="file"
            accept="image/*"
            onChange={handleImageUpload}
            className="file-input"
          />
        </div>

        {image && (
          <div className="image-section">
            <h3>Click two points on the image to define the split line:</h3>
            <div className="canvas-container">
              <canvas
                ref={canvasRef}
                onClick={handleCanvasClick}
                style={{ border: '1px solid #ccc', cursor: 'crosshair' }}
              />
              <img
                ref={imageRef}
                src={image}
                alt="Uploaded"
                style={{ display: 'none' }}
                onLoad={handleImageLoad}
              />
            </div>
            <p>Points selected: {points.length}/2</p>
            <button onClick={clearPoints} className="clear-button">Clear Points</button>
          </div>
        )}

        {points.length === 2 && (
          <div className="question-section">
            <h3>Ask a question about the relationship between the two parts:</h3>
            <textarea
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="e.g., What is the difference between the left and right parts?"
              className="question-input"
            />
            <button
              onClick={handleAnalyze}
              disabled={loading}
              className="analyze-button"
            >
              {loading ? 'Analyzing...' : 'Analyze'}
            </button>
            <div className="status">
              vLLM Status: {vllmReady ? '✅ Ready' : '⚠️ Starting up (using mock responses)'}
            </div>
          </div>
        )}

        {response && (
          <div className="response-section">
            <h3>Analysis Result:</h3>
            <div className="response-text">{response}</div>
          </div>
        )}

        {splitImages.image1 && splitImages.image2 && (
          <div className="split-images-section">
            <h3>Split Images:</h3>
            <div className="split-images-container">
              <div className="split-image">
                <h4>Part 1</h4>
                <img
                  src={`data:image/png;base64,${splitImages.image1}`}
                  alt="Split part 1"
                />
              </div>
              <div className="split-image">
                <h4>Part 2</h4>
                <img
                  src={`data:image/png;base64,${splitImages.image2}`}
                  alt="Split part 2"
                />
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}

export default App;