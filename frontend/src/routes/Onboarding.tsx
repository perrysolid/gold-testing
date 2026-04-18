// TODO [FR-1.1, FR-1.2, FR-1.3]: Phone OTP → KYC form → consent screen
// Stub: navigate directly to capture for scaffold phase
import { useEffect } from "react";
import { useNavigate } from "react-router-dom";

export default function Onboarding() {
  const navigate = useNavigate();
  useEffect(() => { navigate("/capture"); }, [navigate]);
  return <div className="min-h-screen bg-ivory flex items-center justify-center">Loading…</div>;
}
