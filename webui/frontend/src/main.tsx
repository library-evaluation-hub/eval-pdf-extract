import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import "./index.css";
import Layout from "./Layout";
import Dashboard from "./pages/Dashboard";
import Runs from "./pages/Runs";
import Adapters from "./pages/Adapters";
import Fixtures from "./pages/Fixtures";
import Compare from "./pages/Compare";
import FixtureDetail from "./pages/FixtureDetail";
import AdapterDetail from "./pages/AdapterDetail";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<Dashboard />} />
          <Route path="/runs" element={<Runs />} />
          <Route path="/adapters" element={<Adapters />} />
          <Route path="/fixtures" element={<Fixtures />} />
          <Route path="/compare" element={<Compare />} />
          <Route path="/fixture/:fixtureId" element={<FixtureDetail />} />
          <Route path="/adapter/:adapterId" element={<AdapterDetail />} />
        </Route>
      </Routes>
    </BrowserRouter>
  </React.StrictMode>,
);
