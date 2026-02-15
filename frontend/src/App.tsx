import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { Layout } from './components/Layout';
import Dashboard from './pages/Dashboard';
import { PersonaLibrary } from './pages/PersonaLibrary';
import BrandLibrary from './pages/BrandLibrary';
import { CreatePersona } from './pages/CreatePersona';
import { SimulationHub } from './pages/SimulationHub';
import { Analytics } from './pages/Analytics';
import { ComparePersonas } from './pages/ComparePersonas';
import { KnowledgeGraphPage } from './pages/KnowledgeGraphPage';
import { PersonaChat } from './pages/PersonaChat';

function App() {
  return (
    <Router>
      <Routes>
        <Route path="/chat/:sessionId" element={<PersonaChat />} />
        <Route path="/" element={<Layout />}>
          <Route index element={<Dashboard />} />
          <Route path="personas" element={<PersonaLibrary />} />
          <Route path="brand-library" element={<BrandLibrary />} />
          <Route path="knowledge-graph" element={<KnowledgeGraphPage />} />
          <Route path="create-persona" element={<CreatePersona />} />
          <Route path="simulation" element={<SimulationHub />} />
          <Route path="analytics" element={<Analytics />} />
          <Route path="compare" element={<ComparePersonas />} />
        </Route>
      </Routes>
    </Router>
  );
}

export default App;
