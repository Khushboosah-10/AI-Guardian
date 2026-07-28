import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from "recharts";
import { Shield, Camera, AlertTriangle, Search, Play, Square, RefreshCw, Download, Trash2, ChevronRight } from "lucide-react";

const API = "http://localhost:8001";

const SEVERITY_COLORS = {
  normal:    "#22c55e",
  person:    "#eab308",
  loitering: "#f97316",
  garbage:   "#f97316",
  vehicle:   "#f97316",
  vandalism: "#ef4444",
  animal:    "#eab308",
};

const SEVERITY_LABELS = {
  normal:    "🟢 Normal",
  person:    "🟡 Person",
  loitering: "🟠 Loitering",
  garbage:   "🟠 Garbage",
  vehicle:   "🟠 Vehicle",
  vandalism: "🔴 Vandalism",
  animal:    "🟡 Animal",
};

export default function App() {
  const [tab, setTab] = useState("dashboard");
  const [stats, setStats] = useState(null);
  const [incidents, setIncidents] = useState([]);
  const [cameras, setCameras] = useState([]);
  const [snapshots, setSnapshots] = useState({});
  const [monitoring, setMonitoring] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState(null);
  const [searching, setSearching] = useState(false);
  const [selectedIncident, setSelectedIncident] = useState(null);
  const [loading, setLoading] = useState(false);
  const [filter, setFilter] = useState({ cam: "", severity: "" });

  const fetchStats = useCallback(async () => {
    try {
      const r = await axios.get(`${API}/stats`);
      setStats(r.data);
      setMonitoring(r.data.monitoring);
    } catch {}
  }, []);

  const fetchIncidents = useCallback(async () => {
    try {
      const params = {};
      if (filter.cam) params.cam_id = filter.cam;
      if (filter.severity) params.severity = filter.severity;
      const r = await axios.get(`${API}/incidents`, { params });
      setIncidents(r.data.incidents || []);
    } catch {}
  }, [filter]);

  const fetchCameras = useCallback(async () => {
    try {
      const r = await axios.get(`${API}/cameras`);
      setCameras(r.data.cameras || []);
    } catch {}
  }, []);

  const fetchSnapshot = async (camId) => {
    try {
      const r = await axios.get(`${API}/cameras/${camId}/snapshot`);
      setSnapshots(prev => ({ ...prev, [camId]: `${API}${r.data.url}?t=${Date.now()}` }));
    } catch {}
  };

  useEffect(() => {
    fetchStats();
    fetchIncidents();
    fetchCameras();
    const interval = setInterval(() => {
      fetchStats();
      fetchIncidents();
    }, 5000);
    return () => clearInterval(interval);
  }, [fetchStats, fetchIncidents]);

  const toggleMonitoring = async () => {
    setLoading(true);
    try {
      if (monitoring) {
        await axios.post(`${API}/monitoring/stop`);
        setMonitoring(false);
      } else {
        await axios.post(`${API}/monitoring/start`);
        setMonitoring(true);
      }
    } catch {}
    setLoading(false);
  };

  const handleSearch = async () => {
    if (!searchQuery.trim()) return;
    setSearching(true);
    try {
      const r = await axios.post(`${API}/incidents/search`, { query: searchQuery });
      setSearchResults(r.data.results || []);
    } catch {}
    setSearching(false);
  };

  const deleteIncident = async (id) => {
    await axios.delete(`${API}/incidents/${id}`);
    fetchIncidents();
    setSelectedIncident(null);
  };

  const displayIncidents = searchResults !== null ? searchResults : incidents;

  const pieData = stats ? Object.entries(stats.by_severity || {}).map(([k, v]) => ({
    name: SEVERITY_LABELS[k] || k, value: v, color: SEVERITY_COLORS[k] || "#888"
  })) : [];

  const barData = stats ? Object.entries(stats.by_camera || {}).map(([k, v]) => ({
    name: k.length > 15 ? k.slice(0, 15) + "..." : k, incidents: v
  })) : [];

  return (
    <div style={{ minHeight: "100vh", background: "#0a0f1a", color: "#e2e8f0", fontFamily: "system-ui, sans-serif" }}>
      {/* Header */}
      <div style={{ background: "#0d1526", borderBottom: "1px solid #1e293b", padding: "12px 24px", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <Shield size={28} color="#3b82f6" />
          <div>
            <div style={{ fontSize: 20, fontWeight: 700, color: "#f1f5f9" }}>AI Guardian</div>
            <div style={{ fontSize: 11, color: "#64748b" }}>Smart CCTV Security System</div>
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13, color: monitoring ? "#22c55e" : "#64748b" }}>
            <div style={{ width: 8, height: 8, borderRadius: "50%", background: monitoring ? "#22c55e" : "#64748b", animation: monitoring ? "pulse 2s infinite" : "none" }} />
            {monitoring ? "Monitoring Active" : "Monitoring Stopped"}
          </div>
          <button
            onClick={toggleMonitoring}
            disabled={loading}
            style={{
              display: "flex", alignItems: "center", gap: 6,
              padding: "8px 16px", borderRadius: 8, border: "none",
              background: monitoring ? "#ef4444" : "#3b82f6",
              color: "#fff", cursor: "pointer", fontSize: 13, fontWeight: 600,
            }}
          >
            {monitoring ? <><Square size={14} /> Stop</> : <><Play size={14} /> Start</>}
          </button>
        </div>
      </div>

      {/* Nav */}
      <div style={{ background: "#0d1526", borderBottom: "1px solid #1e293b", padding: "0 24px", display: "flex", gap: 0 }}>
        {[
          { id: "dashboard", label: "Dashboard" },
          { id: "cameras", label: "Live Cameras" },
          { id: "incidents", label: `Incidents (${stats?.total_incidents || 0})` },
          { id: "search", label: "AI Search" },
        ].map(t => (
          <button key={t.id} onClick={() => setTab(t.id)} style={{
            padding: "12px 20px", background: "none", border: "none",
            borderBottom: tab === t.id ? "2px solid #3b82f6" : "2px solid transparent",
            color: tab === t.id ? "#3b82f6" : "#94a3b8",
            cursor: "pointer", fontSize: 14, fontWeight: tab === t.id ? 600 : 400,
          }}>{t.label}</button>
        ))}
      </div>

      <div style={{ padding: 24, maxWidth: 1400, margin: "0 auto" }}>

        {/* DASHBOARD TAB */}
        {tab === "dashboard" && (
          <div>
            {/* Stats cards */}
            <div style={{fontSize: 12, color: "#64748b", marginBottom: 16, textAlign: "right"}}>
            🔄 Auto-refreshes every 5 seconds
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 16, marginBottom: 24 }}>
              {[
                { label: "Total Incidents", value: stats?.total_incidents || 0, color: "#3b82f6", icon: "🚨" },
                { label: "Today", value: stats?.today_incidents || 0, color: "#f97316", icon: "📅" },
                { label: "Cameras Active", value: stats?.cameras_active || 0, color: "#22c55e", icon: "📹" },
                { label: "Status", value: monitoring ? "LIVE" : "OFF", color: monitoring ? "#22c55e" : "#ef4444", icon: "🛡️" },
              ].map((s, i) => (
                <div key={i} style={{ background: "#0d1526", border: "1px solid #1e293b", borderRadius: 12, padding: 20 }}>
                  <div style={{ fontSize: 24, marginBottom: 4 }}>{s.icon}</div>
                  <div style={{ fontSize: 28, fontWeight: 700, color: s.color }}>{s.value}</div>
                  <div style={{ fontSize: 13, color: "#64748b" }}>{s.label}</div>
                </div>
              ))}
            </div>

            {/* Charts */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 24 }}>
              <div style={{ background: "#0d1526", border: "1px solid #1e293b", borderRadius: 12, padding: 20 }}>
                <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 16, color: "#94a3b8" }}>Incidents by Camera</div>
                {barData.length > 0 ? (
                  <ResponsiveContainer width="100%" height={200}>
                    <BarChart data={barData}>
                      <XAxis dataKey="name" tick={{ fill: "#64748b", fontSize: 11 }} />
                      <YAxis tick={{ fill: "#64748b", fontSize: 11 }} />
                      <Tooltip contentStyle={{ background: "#1e293b", border: "none", borderRadius: 8 }} />
                      <Bar dataKey="incidents" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                ) : <div style={{ color: "#64748b", textAlign: "center", padding: 40 }}>No data yet</div>}
              </div>

              <div style={{ background: "#0d1526", border: "1px solid #1e293b", borderRadius: 12, padding: 20 }}>
                <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 16, color: "#94a3b8" }}>Incidents by Severity</div>
                {pieData.length > 0 ? (
                  <ResponsiveContainer width="100%" height={200}>
                    <PieChart>
                      <Pie data={pieData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={80} label={({ name, value }) => `${name}: ${value}`}>
                        {pieData.map((entry, i) => <Cell key={i} fill={entry.color} />)}
                      </Pie>
                      <Tooltip contentStyle={{ background: "#1e293b", border: "none", borderRadius: 8 }} />
                    </PieChart>
                  </ResponsiveContainer>
                ) : <div style={{ color: "#64748b", textAlign: "center", padding: 40 }}>No data yet</div>}
              </div>
            </div>

            {/* Recent incidents */}
            <div style={{ background: "#0d1526", border: "1px solid #1e293b", borderRadius: 12, padding: 20 }}>
              <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 16, color: "#94a3b8" }}>Recent Incidents</div>
              {incidents.slice(0, 5).map(inc => (
                <div key={inc.id} onClick={() => { setSelectedIncident(inc); setTab("incidents"); }}
                  style={{ display: "flex", alignItems: "center", gap: 12, padding: "10px 0", borderBottom: "1px solid #1e293b", cursor: "pointer" }}>
                  <div style={{ fontSize: 20 }}>{inc.severity_emoji}</div>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: 13, fontWeight: 500 }}>{inc.severity_label}</div>
                    <div style={{ fontSize: 12, color: "#64748b" }}>{inc.cam_name} • {new Date(inc.timestamp).toLocaleString()}</div>
                  </div>
                  <ChevronRight size={16} color="#64748b" />
                </div>
              ))}
              {incidents.length === 0 && <div style={{ color: "#64748b", textAlign: "center", padding: 20 }}>No incidents yet</div>}
            </div>
          </div>
        )}

        {/* CAMERAS TAB */}
        {tab === "cameras" && (
          <div>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
              <div style={{ fontSize: 16, fontWeight: 600 }}>Live Camera Feeds</div>
              <button onClick={() => cameras.forEach(c => fetchSnapshot(c.id))}
                style={{ display: "flex", alignItems: "center", gap: 6, padding: "8px 16px", borderRadius: 8, border: "1px solid #1e293b", background: "none", color: "#94a3b8", cursor: "pointer", fontSize: 13 }}>
                <RefreshCw size={14} /> Refresh All
              </button>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 16 }}>
              {cameras.map(cam => (
                <div key={cam.id} style={{ background: "#0d1526", border: "1px solid #1e293b", borderRadius: 12, overflow: "hidden" }}>
                  <div style={{ position: "relative", background: "#000", aspectRatio: "16/9", display: "flex", alignItems: "center", justifyContent: "center" }}>
                    {snapshots[cam.id] ? (
                      <img src={snapshots[cam.id]} alt={cam.name} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
                    ) : (
                      <div style={{ textAlign: "center", color: "#64748b" }}>
                        <Camera size={32} style={{ marginBottom: 8 }} />
                        <div style={{ fontSize: 12 }}>Click to load</div>
                      </div>
                    )}
                    <div style={{ position: "absolute", top: 8, left: 8, background: "rgba(0,0,0,0.7)", padding: "2px 8px", borderRadius: 4, fontSize: 11, color: "#22c55e" }}>
                      CAM{cam.id}
                    </div>
                  </div>
                  <div style={{ padding: 12, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <div>
                      <div style={{ fontSize: 13, fontWeight: 500 }}>{cam.name}</div>
                      <div style={{ fontSize: 11, color: "#64748b" }}>Channel {cam.id}</div>
                    </div>
                    <button onClick={() => fetchSnapshot(cam.id)}
                      style={{ padding: "6px 12px", borderRadius: 6, border: "1px solid #3b82f6", background: "none", color: "#3b82f6", cursor: "pointer", fontSize: 12 }}>
                      Snapshot
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* INCIDENTS TAB */}
        {tab === "incidents" && (
          <div style={{ display: "grid", gridTemplateColumns: selectedIncident ? "1fr 1fr" : "1fr", gap: 16 }}>
            <div>
              {/* Filters */}
              <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
                <select value={filter.cam} onChange={e => setFilter(f => ({ ...f, cam: e.target.value }))}
                  style={{ background: "#0d1526", border: "1px solid #1e293b", color: "#94a3b8", padding: "8px 12px", borderRadius: 8, fontSize: 13 }}>
                  <option value="">All Cameras</option>
                  {cameras.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
                </select>
                <select value={filter.severity} onChange={e => setFilter(f => ({ ...f, severity: e.target.value }))}
                  style={{ background: "#0d1526", border: "1px solid #1e293b", color: "#94a3b8", padding: "8px 12px", borderRadius: 8, fontSize: 13 }}>
                  <option value="">All Severity</option>
                  {Object.entries(SEVERITY_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                </select>
                <button onClick={fetchIncidents}
                  style={{ padding: "8px 16px", borderRadius: 8, border: "1px solid #1e293b", background: "none", color: "#94a3b8", cursor: "pointer", fontSize: 13 }}>
                  <RefreshCw size={14} />
                </button>
              </div>

              {/* Incident list */}
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                {displayIncidents.map(inc => (
                  <div key={inc.id} onClick={() => setSelectedIncident(inc)}
                    style={{
                      background: selectedIncident?.id === inc.id ? "#1e293b" : "#0d1526",
                      border: `1px solid ${selectedIncident?.id === inc.id ? "#3b82f6" : "#1e293b"}`,
                      borderRadius: 12, padding: 16, cursor: "pointer",
                      display: "flex", gap: 12, alignItems: "center",
                    }}>
                    {inc.image && (
                      <img src={`${API}/captures/images/${inc.image}`} alt=""
                        style={{ width: 64, height: 64, borderRadius: 8, objectFit: "cover", flexShrink: 0 }} />
                    )}
                    <div style={{ flex: 1 }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                        <span style={{ fontSize: 18 }}>{inc.severity_emoji}</span>
                        <span style={{ fontSize: 14, fontWeight: 600 }}>{inc.severity_label}</span>
                        <span style={{ fontSize: 11, padding: "2px 8px", borderRadius: 4, background: "#1e293b", color: "#64748b" }}>
                          {inc.cam_name}
                        </span>
                      </div>
                      <div style={{ fontSize: 12, color: "#64748b" }}>
                        {new Date(inc.timestamp).toLocaleString()} • {inc.detections?.map(d => d.class).join(", ")}
                      </div>
                    </div>
                    <ChevronRight size={16} color="#64748b" />
                  </div>
                ))}
                {displayIncidents.length === 0 && (
                  <div style={{ textAlign: "center", color: "#64748b", padding: 40 }}>No incidents found</div>
                )}
              </div>
            </div>

            {/* Incident detail */}
            {selectedIncident && (
              <div style={{ background: "#0d1526", border: "1px solid #1e293b", borderRadius: 12, padding: 20, position: "sticky", top: 20, maxHeight: "80vh", overflowY: "auto" }}>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 16 }}>
                  <div style={{ fontSize: 16, fontWeight: 600 }}>Incident Details</div>
                  <button onClick={() => setSelectedIncident(null)}
                    style={{ background: "none", border: "none", color: "#64748b", cursor: "pointer", fontSize: 18 }}>×</button>
                </div>

                {selectedIncident.image && (
                  <img src={`${API}/captures/images/${selectedIncident.image}`} alt="incident"
                    style={{ width: "100%", borderRadius: 8, marginBottom: 16 }} />
                )}

                <div style={{ display: "flex", flexDirection: "column", gap: 8, marginBottom: 16 }}>
                  {[
                    ["ID", selectedIncident.id],
                    ["Camera", selectedIncident.cam_name],
                    ["Time", new Date(selectedIncident.timestamp).toLocaleString()],
                    ["Severity", `${selectedIncident.severity_emoji} ${selectedIncident.severity_label}`],
                    ["Detected", selectedIncident.detections?.map(d => `${d.class} (${Math.round(d.confidence * 100)}%)`).join(", ")],
                  ].map(([k, v]) => (
                    <div key={k} style={{ display: "flex", gap: 8 }}>
                      <span style={{ fontSize: 12, color: "#64748b", width: 80, flexShrink: 0 }}>{k}</span>
                      <span style={{ fontSize: 12 }}>{v}</span>
                    </div>
                  ))}
                </div>

                {selectedIncident.events?.length > 0 && (
                  <div style={{ background: "#1e293b", borderRadius: 8, padding: 12, marginBottom: 16 }}>
                    <div style={{ fontSize: 12, color: "#64748b", marginBottom: 8 }}>Events</div>
                    {selectedIncident.events.map((e, i) => (
                      <div key={i} style={{ fontSize: 13, color: "#f97316" }}>⚠️ {e.message}</div>
                    ))}
                  </div>
                )}

                <div style={{ display: "flex", gap: 8 }}>
                  {selectedIncident.image && (
                    <a href={`${API}/captures/images/${selectedIncident.image}`} download
                      style={{ display: "flex", alignItems: "center", gap: 6, padding: "8px 14px", borderRadius: 8, border: "1px solid #3b82f6", color: "#3b82f6", textDecoration: "none", fontSize: 13 }}>
                      <Download size={14} /> Download
                    </a>
                  )}
                  <button onClick={() => deleteIncident(selectedIncident.id)}
                    style={{ display: "flex", alignItems: "center", gap: 6, padding: "8px 14px", borderRadius: 8, border: "1px solid #ef4444", background: "none", color: "#ef4444", cursor: "pointer", fontSize: 13 }}>
                    <Trash2 size={14} /> Delete
                  </button>
                </div>
              </div>
            )}
          </div>
        )}

        {/* AI SEARCH TAB */}
        {tab === "search" && (
          <div>
            <div style={{ background: "#0d1526", border: "1px solid #1e293b", borderRadius: 12, padding: 24, marginBottom: 24 }}>
              <div style={{ fontSize: 16, fontWeight: 600, marginBottom: 8 }}>🤖 AI-Powered Search</div>
              <div style={{ fontSize: 13, color: "#64748b", marginBottom: 16 }}>
                Search incidents using natural language
              </div>
              <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
                <input
                  value={searchQuery}
                  onChange={e => setSearchQuery(e.target.value)}
                  onKeyDown={e => e.key === "Enter" && handleSearch()}
                  placeholder='e.g. "person near gate after 10pm" or "all garbage incidents today"'
                  style={{ flex: 1, background: "#1e293b", border: "1px solid #334155", color: "#e2e8f0", padding: "10px 16px", borderRadius: 8, fontSize: 14, outline: "none" }}
                />
                <button onClick={handleSearch} disabled={searching}
                  style={{ display: "flex", alignItems: "center", gap: 6, padding: "10px 20px", borderRadius: 8, border: "none", background: "#3b82f6", color: "#fff", cursor: "pointer", fontSize: 14, fontWeight: 600 }}>
                  <Search size={16} /> {searching ? "Searching..." : "Search"}
                </button>
              </div>
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                {["Show all loitering incidents", "Vehicles detected today", "Person near entrance gate", "All incidents this week"].map(q => (
                  <button key={q} onClick={() => { setSearchQuery(q); }}
                    style={{ padding: "6px 12px", borderRadius: 20, border: "1px solid #334155", background: "none", color: "#94a3b8", cursor: "pointer", fontSize: 12 }}>
                    {q}
                  </button>
                ))}
              </div>
            </div>

            {searchResults !== null && (
              <div>
                <div style={{ fontSize: 14, color: "#64748b", marginBottom: 12 }}>
                  Found {searchResults.length} results for "{searchQuery}"
                  <button onClick={() => { setSearchResults(null); setSearchQuery(""); }}
                    style={{ marginLeft: 12, background: "none", border: "none", color: "#3b82f6", cursor: "pointer", fontSize: 13 }}>
                    Clear
                  </button>
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                  {searchResults.map(inc => (
                    <div key={inc.id} style={{ background: "#0d1526", border: "1px solid #1e293b", borderRadius: 12, padding: 16, display: "flex", gap: 12 }}>
                      {inc.image && (
                        <img src={`${API}/captures/images/${inc.image}`} alt=""
                          style={{ width: 80, height: 60, borderRadius: 8, objectFit: "cover", flexShrink: 0 }} />
                      )}
                      <div>
                        <div style={{ fontSize: 14, fontWeight: 500, marginBottom: 4 }}>
                          {inc.severity_emoji} {inc.severity_label} — {inc.cam_name}
                        </div>
                        <div style={{ fontSize: 12, color: "#64748b" }}>
                          {new Date(inc.timestamp).toLocaleString()} • {inc.detections?.map(d => d.class).join(", ")}
                        </div>
                      </div>
                    </div>
                  ))}
                  {searchResults.length === 0 && (
                    <div style={{ textAlign: "center", color: "#64748b", padding: 40 }}>No matching incidents found</div>
                  )}
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.4; }
        }
        * { box-sizing: border-box; }
        ::-webkit-scrollbar { width: 6px; }
        ::-webkit-scrollbar-track { background: #0d1526; }
        ::-webkit-scrollbar-thumb { background: #334155; border-radius: 3px; }
      `}</style>
    </div>
  );
}
