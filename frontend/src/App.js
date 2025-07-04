import React, { useState, useRef, useCallback } from 'react';
import './App.css';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8000';

function App() {
  const [selectedFile, setSelectedFile] = useState(null);
  const [imagePreview, setImagePreview] = useState(null);
  const [points, setPoints] = useState([]);
  const [question, setQuestion] = useState('');
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [splitImages, setSplitImages] = useState({ image1: null, image2: null });

  const canvasRef = useRef(null);
  const imageRef = useRef(null);

  const handleFileChange = (event) => {
    const file = event.target.files[0];
    if (file) {
      setSelectedFile(file);
      setPoints([]);
      setResult(null);
      setError('');
      setSplitImages({ image1: null, image2: null });

      // Create preview
      const reader = new FileReader();
      reader.onload = (e) => {
        setImagePreview(e.target.result);
      };
      reader.readAsDataURL(file);
    }
  };

  const getImageCoordinates = useCallback((event) => {
    const canvas = canvasRef.current;
    const rect = canvas.getBoundingClientRect();
    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;

    const x = (event.clientX - rect.left) * scaleX;
    const y = (event.clientY - rect.top) * scaleY;

    // Convert to relative coordinates (0-1)
    const relativeX = x / canvas.width;
    const relativeY = y / canvas.height;

    return { x: relativeX, y: relativeY, pixelX: x, pixelY: y };
  }, []);

  const handleCanvasClick = (event) => {
    if (points.length >= 2) {
      setPoints([]);
      redrawCanvas();
    }

    const coords = getImageCoordinates(event);
    const newPoints = [...points, coords];
    setPoints(newPoints);

    // Redraw canvas with points
    redrawCanvas(newPoints);
  };

  const redrawCanvas = (currentPoints = points) => {
    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    const img = imageRef.current;

    if (!img) return;

    // Clear canvas
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Draw image
    ctx.drawImage(img, 0, 0, canvas.width, canvas.height);

    // Draw points
    currentPoints.forEach((point, index) => {
      ctx.beginPath();
      ctx.arc(point.pixelX, point.pixelY, 8, 0, 2 * Math.PI);
      ctx.fillStyle = index === 0 ? '#ff0000' : '#00ff00';
      ctx.fill();
      ctx.strokeStyle = '#ffffff';
      ctx.lineWidth = 2;
      ctx.stroke();

      // Add point label
      ctx.fillStyle = '#ffffff';
      ctx.font = '14px Arial';
      ctx.fillText(`P${index + 1}`, point.pixelX + 12, point.pixelY - 8);
    });

    // Draw line between points
    if (currentPoints.length === 2) {
      ctx.beginPath();
      ctx.moveTo(currentPoints[0].pixelX, currentPoints[0].pixelY);
      ctx.lineTo(currentPoints[1].pixelX, currentPoints[1].pixelY);
      ctx.strokeStyle = '#ffff00';
      ctx.lineWidth = 3;
      ctx.stroke();

      // Draw line extension to show split
      const p1 = currentPoints[0];
      const p2 = currentPoints[1];

      // Calculate line direction
      const dx = p2.pixelX - p1.pixelX;
      const dy = p2.pixelY - p1.pixelY;
      const length = Math.sqrt(dx * dx + dy * dy);

      if (length > 0) {
        const unitX = dx / length;
        const unitY = dy / length;

        // Extend line to canvas edges
        const extendLength = Math.max(canvas.width, canvas.height);

        ctx.beginPath();
        ctx.moveTo(p1.pixelX - unitX * extendLength, p1.pixelY - unitY * extendLength);
        ctx.lineTo(p1.pixelX + unitX * extendLength, p1.pixelY + unitY * extendLength);
        ctx.strokeStyle = '#ffff00';
        ctx.lineWidth = 2;
        ctx.globalAlpha = 0.7;
        ctx.stroke();
        ctx.globalAlpha = 1.0;
      }
    }
  };

  const handleImageLoad = () => {
    const canvas = canvasRef.current;
    const img = imageRef.current;

    if (!img || !canvas) return;

    // Set canvas size to match image display size
    const maxWidth = 800;
    const maxHeight = 600;

    let { width, height } = img;

    // Scale to fit container
    if (width > maxWidth || height > maxHeight) {
      const scale = Math.min(maxWidth / width, maxHeight / height);
      width = width * scale;
      height = height * scale;
    }

    canvas.width = width;
    canvas.height = height;

    // Initial draw
    redrawCanvas();
  };

  const handleSubmit = async () => {
    if (!selectedFile || points.length !== 2 || !question.trim()) {
      setError('Please select an image, place 2 points, and enter a question.');
      return;
    }

    setLoading(true);
    setError('');
    setResult(null);

    try {
      // Convert file to base64
      const base64 = await fileToBase64(selectedFile);

      const payload = {
        image_base64: base64.split(',')[1], // Remove data:image/...;base64, prefix
        point1: { x: points[0].x, y: points[0].y },
        point2: { x: points[1].x, y: points[1].y },
        question: question
      };

      const response = await fetch(`${BACKEND_URL}/api/split-image`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();

      if (data.success) {
        setResult(data.answer);
        setSplitImages({
          image1: data.image1_base64,
          image2: data.image2_base64
        });
      } else {
        setError(data.error || 'Failed to process image');
      }

    } catch (err) {
      setError(`Error: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const fileToBase64 = (file) => {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.readAsDataURL(file);
      reader.onload = () => resolve(reader.result);
      reader.onerror = error => reject(error);
    });
  };

  const resetAll = () => {
    setSelectedFile(null);
    setImagePreview(null);
    setPoints([]);
    setQuestion('');
    setResult(null);
    setError('');
    setSplitImages({ image1: null, image2: null });
  };

  return (
    <div className="App">
      <div className="container">
        <h1>Image Splitter & Multimodal Analysis</h1>

        <div className="upload-section">
          <input
            type="file"
            accept="image/*"
            onChange={handleFileChange}
            id="file-input"
            className="file-input"
          />
          <label htmlFor="file-input" className="file-label">
            Choose Image
          </label>
          {selectedFile && (
            <span className="file-name">{selectedFile.name}</span>
          )}
        </div>

        {imagePreview && (
          <div className="image-section">
            <h3>Click two points to define the split line:</h3>
            <div className="image-container">
              <img
                ref={imageRef}
                src={imagePreview}
                alt="Preview"
                style={{ display: 'none' }}
                onLoad={handleImageLoad}
              />
              <canvas
                ref={canvasRef}
                onClick={handleCanvasClick}
                className="image-canvas"
              />
            </div>
            <div className="points-info">
              <p>Points selected: {points.length}/2</p>
              {points.length > 0 && (
                <div className="point-details">
                  {points.map((point, index) => (
                    <span key={index} className="point-detail">
                      P{index + 1}: ({Math.round(point.x * 100)}%, {Math.round(point.y * 100)}%)
                    </span>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {points.length === 2 && (
          <div className="question-section">
            <h3>Ask a question about the relationship between the two image parts:</h3>
            <textarea
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="e.g., What is the difference between the left and right parts of the image?"
              className="question-input"
            />
            <button
              onClick={handleSubmit}
              disabled={loading || !question.trim()}
              className="submit-button"
            >
              {loading ? 'Analyzing...' : 'Analyze Images'}
            </button>
          </div>
        )}

        {error && (
          <div className="error-message">
            {error}
          </div>
        )}

        {result && (
          <div className="result-section">
            <h3>Analysis Result:</h3>
            <div className="result-content">
              <p>{result}</p>
            </div>
          </div>
        )}

        {splitImages.image1 && splitImages.image2 && (
          <div className="split-images-section">
            <h3>Split Images:</h3>
            <div className="split-images-container">
              <div className="split-image">
                <h4>Image Part 1</h4>
                <img
                  src={`data:image/png;base64,${splitImages.image1}`}
                  alt="Split part 1"
                  className="split-image-display"
                />
              </div>
              <div className="split-image">
                <h4>Image Part 2</h4>
                <img
                  src={`data:image/png;base64,${splitImages.image2}`}
                  alt="Split part 2"
                  className="split-image-display"
                />
              </div>
            </div>
          </div>
        )}

        <div className="controls">
          <button onClick={resetAll} className="reset-button">
            Reset All
          </button>
        </div>
      </div>
    </div>
  );
}

export default App;