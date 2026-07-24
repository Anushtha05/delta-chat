import { Routes, Route } from 'react-router-dom';
import Layout from './components/Layout';
import Landing from './pages/Landing';
import Compare from './pages/Compare';
import Chat from './pages/Chat';
import Evaluation from './pages/Evaluation';

function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Landing />} />
        <Route path="/compare" element={<Compare />} />
        <Route path="/chat" element={<Chat />} />
        <Route path="/evaluation" element={<Evaluation />} />
      </Route>
    </Routes>
  );
}

export default App;
