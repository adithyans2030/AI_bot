import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import App from "./App.jsx";
import LandingPage from "./pages/LandingPage.jsx";
import { captureTokenFromUrl } from "./api.js";
import "./styles.css";

// After a Moodle launch the backend lands here with #token=...; store it
// before anything renders or calls the API.
captureTokenFromUrl();

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/app" element={<App />} />
      </Routes>
    </BrowserRouter>
  </React.StrictMode>
);
