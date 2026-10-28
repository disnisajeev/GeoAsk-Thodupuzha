import React from 'react';
import { NavLink } from 'react-router-dom';
import { Home, Search, Map, Layers, HelpCircle, History } from 'lucide-react';

export default function Sidebar() {
  const navs = [
    { name: 'Home', path: '/', icon: <Home size={18} /> },
    { name: 'Geo Query', path: '/query', icon: <Search size={18} /> },
    { name: 'Explore Map', path: '/explore', icon: <Map size={18} /> },
    /*{ name: 'Layer Explorer', path: '/layers', icon: <Layers size={18} /> },*/
    { name: 'Recent Queries', path: '/history', icon: <History size={18} /> },
  ];

  return (
    <aside className="w-64 bg-[#0f3d2e] text-white flex flex-col h-screen fixed left-0 top-0 shadow-lg z-50">
      <div className="p-6 border-b border-green-800 flex items-center gap-3">
        <div className="bg-green-500 p-2 rounded-lg text-xl">🌍</div>
        <div>
          <h1 className="text-xl font-bold leading-tight">GeoAsk</h1>
        </div>
      </div>
      
      <nav className="flex-1 py-4 space-y-1">
        {navs.map((n) => (
          <NavLink 
            key={n.name} 
            to={n.path} 
            className={({isActive}) => 
              `flex items-center gap-3 px-6 py-3 text-sm font-medium transition-all ${
                isActive 
                  ? 'bg-[#185c46] border-l-4 border-green-400 text-white' 
                  : 'text-green-100 hover:bg-[#144d3a] hover:text-white'
              }`
            }
          >
            {n.icon} {n.name}
          </NavLink>
        ))}
      </nav>

      {/* Clean bottom branding instead of the fake map box */}
      <div className="p-6 border-t border-green-800 text-xs text-green-400">
        <p>RAG-LLM Spatial Interface</p>
      </div>
    </aside>
  );
}