import { BrowserRouter, Route, Routes } from "react-router-dom";
import Home from "./routes/Home";
import Onboarding from "./routes/Onboarding";
import Capture from "./routes/Capture";
import Audio from "./routes/Audio";
import Review from "./routes/Review";
import Result from "./routes/Result";
import Lender from "./routes/Lender";
import About from "./routes/About";
import LanguagePicker from "./components/LanguagePicker";

export default function App() {
  return (
    <BrowserRouter>
      {/* Persistent floating language toggle — top-right on every screen */}
      <div className="fixed top-3 right-3 z-50">
        <LanguagePicker />
      </div>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/onboarding" element={<Onboarding />} />
        <Route path="/capture" element={<Capture />} />
        <Route path="/audio" element={<Audio />} />
        <Route path="/review" element={<Review />} />
        <Route path="/result/:id" element={<Result />} />
        <Route path="/lender" element={<Lender />} />
        <Route path="/about" element={<About />} />
      </Routes>
    </BrowserRouter>
  );
}
