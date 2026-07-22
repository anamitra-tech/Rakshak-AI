// src/App.jsx
import { Routes, Route } from 'react-router-dom';
import LandingPage from './sections/LandingPage';
import Login from './sections/Login';
import Walkthrough from './sections/Walkthrough';
import ProtectedRoute from './components/ProtectedRoute';
import CitizenLayout from './Dashboard/citizen/CitizenLayout';
import FraudShield from './Dashboard/citizen/FraudShield';
import Chat from './Dashboard/citizen/Chat';
import Report from './Dashboard/citizen/Report';
import CommandLayout from './Dashboard/CommandWorkSpace/CommandLayout';
import Network from './Dashboard/CommandWorkSpace/Network';
import GeoSpatial from './Dashboard/CommandWorkSpace/GeoSpatial';
import DigitalArrest from './Dashboard/CommandWorkSpace/DigitalArrest';

const App = () => {
  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route path="/login" element={<Login />} />
      <Route path="/walkthrough" element={<Walkthrough />} />

      <Route
        path="/citizen"
        element={
          <ProtectedRoute allowedRole="citizen">
            <CitizenLayout />
          </ProtectedRoute>
        }
      >
        <Route path="fraud-shield" element={<FraudShield />} />
        <Route path="chat" element={<Chat />} />
        <Route path="report" element={<Report />} />
      </Route>

      <Route
        path="/command"
        element={
          <ProtectedRoute allowedRole="government">
            <CommandLayout />
          </ProtectedRoute>
        }
      >
        <Route index element={<Network />} />
        <Route path="network" element={<Network />} />
        <Route path="geospatial" element={<GeoSpatial />} />
        <Route path="digital-arrest" element={<DigitalArrest />} />
      </Route>
    </Routes>
  );
};

export default App;