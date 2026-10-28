import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Sidebar from './components/Sidebar';
import Home from './pages/Home';
import Query from './pages/Query';
import Processing from './pages/Processing';
import Result from './pages/Result';
import Explore from './pages/Explore';

import History from './pages/History';
import LayerExplorer from "./pages/LayerExplorer";

export default function App() {
  return (
    <Router>
      <div className="flex min-h-screen bg-gray-50 font-sans">
        <Sidebar />
        <main className="ml-64 flex-1 p-8 overflow-y-auto h-screen">
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/query" element={<Query />} />
            <Route path="/processing" element={<Processing />} />
            <Route path="/result" element={<Result />} />
            <Route path="/explore" element={<Explore />} />
            <Route path="/layers" element={<LayerExplorer />} />
            <Route path="/history" element={<History />} />
          </Routes>
        </main>
      </div>
    </Router>
  );
}