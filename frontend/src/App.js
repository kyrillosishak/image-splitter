import React, { useState, useRef } from 'react';
import axios from 'axios';
import './App.css';

function App() {
  const [image, setImage] = useState(null);
  const [imageUrl, setImageUrl] = useState('');
  const [points, setPoints] = useState([]);
  const [splitImages, setSplitImages] = useState([]);
  const [question, setQuestion] = useState('');
  const [answer, setAnswer] = useState('');
  const [loading, setLoading] = useState(false);
  const canvasRef = useRef(null);
  const imageRef = useRef(null);

  const handleImageUpload = (event) => {
    const file = event.target.files[0];
    if (file) {
      setImage(file);
      const url = URL.createObjectURL(file);
      setImageUrl(url);
      setPoints([]);
      setSplitImages([]);
      setAnswer('');
    }
  };

  const handleCanvasClick = (event) => {
    if (points.length >= 2) return;

    const canvas = canvasRef.current;
    const rect = canvas.getBoundingClientRect();
    const x = event.clientX - rect.left;
    const y = event.clientY - rect.top;

    const newPoint = { x, y };
    const newPoints = [...points, newPoint];
    setPoints(newPoints);

    // Draw the point
    const ctx = canvas.getContext('2d');
    ctx.fillStyle = 'red';
    ctx.beginPath();
    ctx.arc(x, y, 5, 0, 2 * Math.PI);
    ctx.fill();

    // Draw line if we have 2 points
    if (newPoints.length === 2) {
      ctx.strokeStyle = 'red';
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(newPoints[0].x, newPoints[0].y);
      ctx.lineTo(newPoints[1].x, newPoints[1].y);
      ctx.stroke();
    }
  };

  const handleImageLoad = () => {
    const canvas = canvasRef.current;
    const img = imageRef.current;
    const ctx = canvas.getContext('2d');

    canvas.width = img.width;
    canvas.height = img.height;
    ctx.drawImage(img, 0, 0);
  };

  const splitImage = async () => {
    if (!image || points.length !== 2) return;

    setLoading(true);
    const formData = new FormData();
    formData.append('image', image);
    formData.append('points', JSON.stringify(points));

    try {
      const response = await axios.post('/api/split-image', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      setSplitImages(response.data.split_images);
    } catch (error) {
      console.error('Error splitting image:', error);
      alert('Error splitting image');
    }
    setLoading(false);
  };

  const askQuestion = async () => {
    if (!question || splitImages.length !== 2) return;

    setLoading(true);
    try {
      const response = await axios.post('/api/ask-question', {
        question,
        split_images: splitImages
      });
      setAnswer(response.data.answer);
    } catch (error) {
      console.error('Error asking question:', error);
      alert('Error getting answer from model');
    }
    setLoading(false);
  };

  const resetCanvas = () => {
    setPoints([]);
    setSplitImages([]);
    setAnswer('');
    if (canvasRef.current && imageRef.current) {
      const canvas = canvasRef.current;
      const ctx = canvas.getContext('2d');
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.drawImage(imageRef.current, 0, 0);
    }
  };

  return (
    <div className="App">
      <header className="App-header">
        <h1>Image Splitter & Analyzer</h1>

        <div className="upload-section">
          <input
            type="file"
            accept="image/*"
            onChange={handleImageUpload}
            className="file-input"
          />
        </div>

        {imageUrl && (
          <div className="image-section">
            <div className="image-container">
              <img
                ref={imageRef}
                src={imageUrl}
                alt="Uploaded"
                onLoad={handleImageLoad}
                style={{ display: 'none' }}
              />
              <canvas
                ref={canvasRef}
                onClick={handleCanvasClick}
                className="image-canvas"
              />
            </div>

            <div className="controls">
              <button onClick={resetCanvas}>Reset Points</button>
              <button
                onClick={splitImage}
                disabled={points.length !== 2 || loading}
              >
                {loading ? 'Splitting...' : 'Split Image'}
              </button>
            </div>

            <p className="instructions">
              Click two points on the image to create a split line.
              Points selected: {points.length}/2
            </p>
          </div>
        )}

        {splitImages.length === 2 && (
          <div className="split-images">
            <h3>Split Images</h3>
            <div className="images-row">
              <div className="split-part">
                <h4>Part 1</h4>
                <img src={`data:image/png;base64,${splitImages[0]}`} alt="Part 1" />
              </div>
              <div className="split-part">
                <h4>Part 2</h4>
                <img src={`data:image/png;base64,${splitImages[1]}`} alt="Part 2" />
              </div>
            </div>
          </div>
        )}

        {splitImages.length === 2 && (
          <div className="question-section">
            <h3>Ask a Question</h3>
            <input
              type="text"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="What's the relationship between these two image parts?"
              className="question-input"
            />
            <button
              onClick={askQuestion}
              disabled={!question || loading}
            >
              {loading ? 'Asking...' : 'Ask Question'}
            </button>
          </div>
        )}

        {answer && (
          <div className="answer-section">
            <h3>Answer</h3>
            <p className="answer">{answer}</p>
          </div>
        )}
      </header>
    </div>
  );
}

export default App;