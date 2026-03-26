import React, { useState, useEffect, useCallback } from 'react';
import { 
  Bot, Target, Shield, Zap, TrendingUp, AlertCircle, 
  CheckCircle2, Sparkles, MessageSquare, BrainCircuit, 
  ChevronDown, ChevronUp, Loader2, Send, BarChart3,
  ArrowRight
} from 'lucide-react';
import { inferAssetMeta } from '../utils/assetMeta';

export default function AIPickerPage() {
  const [strategy, setStrategy] = useState('BALANCED');
  const [picks, setPicks] = useState([]);
  const [loading, setLoading] = useState(false);
  
  const [marketInsight, setMarketInsight] = useState('');
  const [insightLoading, setInsightLoading] = useState(false);
  
  const [analysisId, setAnalysisId] = useState(null); 
  const [detailedAnalysis, setDetailedAnalysis] = useState({});
  
  const [customQuestion, setCustomQuestion] = useState('');
  const [chatResponse, setChatResponse] = useState('');
  const [chatLoading, setChatLoading] = useState(false);

  const strategies = [
    { 
      id: 'DEFENSIVE', 
      label: 'Defensive', 
      icon: <Shield size={24} />, 
      desc: 'ความเสี่ยงต่ำ เน้นความมั่นคง ปันผลสม่ำเสมอ', 
      gradient: 'from-emerald-400 to-teal-500',
      bgLight: 'bg-emerald-50 text-emerald-700',
      border: 'border-emerald-200 hover:border-emerald-400'
    },
    { 
      id: 'BALANCED', 
      label: 'Balanced', 
      icon: <Target size={24} />, 
      desc: 'สมดุลระหว่างความเสี่ยงและโอกาสเติบโต', 
      gradient: 'from-blue-500 to-indigo-500',
      bgLight: 'bg-blue-50 text-blue-700',
      border: 'border-blue-200 hover:border-blue-400'
    },
    { 
      id: 'AGGRESSIVE', 
      label: 'Aggressive', 
      icon: <Zap size={24} />, 
      desc: 'เน้นการเติบโตสูง ยอมรับความผันผวนได้', 
      gradient: 'from-rose-500 to-orange-500',
      bgLight: 'bg-rose-50 text-rose-700',
      border: 'border-rose-200 hover:border-rose-400'
    }
  ];

  // Backend AI call: keeps API keys server-side and grounds output on real data pipeline.
  const callAdvisorAPI = async (question) => {
    try {
      const response = await fetch("/api-fastapi/api/ai-advisor", {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          question,
          context: {
            watchlist: picks.map((p) => p.symbol),
            sentiment: null,
            risk_profile: strategy,
          },
        }),
      });

      if (!response.ok) throw new Error('AI API Request Failed');
      const result = await response.json();
      return result?.answer || "ไม่พบข้อมูลวิเคราะห์จากระบบ";
    } catch {
      return "ขออภัย ระบบวิเคราะห์ขัดข้องชั่วคราว โปรดลองใหม่อีกครั้ง";
    }
  };

  const getMarketSummary = async () => {
    setInsightLoading(true);
    const stratObj = strategies.find(s => s.id === strategy);
    const text = await callAdvisorAPI(`สรุปภาพรวมตลาดสำหรับนักลงทุนสไตล์ ${stratObj.label} แบบกระชับ`);
    setMarketInsight(text);
    setInsightLoading(false);
  };

  const analyzeStockDeeply = async (stock) => {
    if (analysisId === stock.symbol) {
      setAnalysisId(null);
      return;
    }
    setAnalysisId(stock.symbol);
    if (detailedAnalysis[stock.symbol]) return; 

    const text = await callAdvisorAPI(`วิเคราะห์หุ้น ${stock.symbol} สำหรับกลยุทธ์ ${strategy} โดยสรุปจุดแข็ง จุดอ่อน ความเสี่ยง และมุมมองการลงทุน`);
    setDetailedAnalysis(prev => ({ ...prev, [stock.symbol]: text }));
  };

  const askCustomQuestion = async (e) => {
    e.preventDefault();
    if (!customQuestion.trim()) return;
    setChatLoading(true);
    const text = await callAdvisorAPI(customQuestion);
    setChatResponse(text);
    setChatLoading(false);
  };

  const fetchPicks = useCallback(async () => {
    setLoading(true);
    try {
      const response = await fetch(`/api-fastapi/ai-picker?strategy=${strategy}&limit=5`);
      if (!response.ok) throw new Error('Network error');
      const data = await response.json();
      setPicks(Array.isArray(data?.items) ? data.items : []);
    } catch {
      setPicks([]);
    } finally {
      setLoading(false);
    }
  }, [strategy]);

  useEffect(() => {
    fetchPicks();
    setMarketInsight('');
    setChatResponse('');
  }, [fetchPicks]);

  return (
    <div className="min-h-screen bg-slate-50/50 p-4 md:p-8 font-sans text-slate-800">
      <div className="max-w-6xl mx-auto space-y-8">
        
        {/* Header Section */}
        <div className="flex flex-col lg:flex-row justify-between items-start lg:items-center gap-6 bg-white p-8 rounded-3xl shadow-sm border border-slate-100 relative overflow-hidden">
          <div className="absolute top-0 right-0 w-64 h-64 bg-indigo-500/10 rounded-full blur-3xl -mr-20 -mt-20"></div>
          
          <div className="relative z-10">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-indigo-50 text-indigo-600 text-sm font-bold mb-4">
              <Sparkles size={16} /> Powered by Live Market AI
            </div>
            <h1 className="text-4xl font-extrabold tracking-tight text-slate-900 flex items-center gap-3">
              <Bot className="w-10 h-10 text-indigo-600" />
              AI Stock Picker
            </h1>
            <p className="text-slate-500 mt-2 text-lg">
              ผู้ช่วยวิเคราะห์พอร์ตและคัดกรองหุ้นด้วยอัลกอริทึมขั้นสูง
            </p>
          </div>
          
          <button 
            onClick={getMarketSummary}
            disabled={insightLoading}
            className="relative z-10 group flex items-center gap-2 px-8 py-4 bg-slate-900 hover:bg-slate-800 text-white rounded-2xl font-bold transition-all shadow-xl shadow-slate-900/20 disabled:opacity-70"
          >
            {insightLoading ? <Loader2 className="w-5 h-5 animate-spin" /> : <BarChart3 className="w-5 h-5 group-hover:scale-110 transition-transform" />}
            สรุปแนวโน้มตลาด
          </button>
        </div>

        {/* AI Insight Card */}
        {marketInsight && (
          <div className="bg-gradient-to-r from-indigo-600 to-violet-600 p-[2px] rounded-3xl animate-in fade-in slide-in-from-top-4 duration-500 shadow-xl shadow-indigo-500/20">
            <div className="bg-white rounded-[22px] p-6 relative overflow-hidden">
              <div className="absolute top-0 right-0 w-32 h-32 bg-indigo-100 rounded-full blur-3xl opacity-50"></div>
              <div className="flex gap-4 relative z-10">
                <div className="bg-indigo-100 p-3 rounded-2xl h-fit">
                  <BrainCircuit className="text-indigo-600 w-6 h-6" />
                </div>
                <div>
                  <h4 className="font-bold text-slate-900 text-lg mb-2 flex items-center gap-2">
                    Market Insight <span className="text-xs font-normal px-2 py-0.5 bg-indigo-100 text-indigo-700 rounded-full">Data-driven Analysis</span>
                  </h4>
                  <div className="text-slate-600 whitespace-pre-line leading-relaxed">
                    {marketInsight}
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Strategy Selector */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {strategies.map((strat) => (
            <button
              key={strat.id}
              onClick={() => setStrategy(strat.id)}
              className={`group relative p-6 rounded-3xl text-left transition-all duration-300 border-2 overflow-hidden
                ${strategy === strat.id 
                  ? 'border-transparent shadow-xl scale-[1.02] bg-white' 
                  : `bg-white ${strat.border} hover:shadow-md hover:-translate-y-1`}
              `}
            >
              {/* Active Gradient Border Background */}
              {strategy === strat.id && (
                <div className={`absolute inset-0 bg-gradient-to-br ${strat.gradient} opacity-5`}></div>
              )}
              {strategy === strat.id && (
                <div className={`absolute top-0 left-0 w-full h-1.5 bg-gradient-to-r ${strat.gradient}`}></div>
              )}

              <div className="relative z-10">
                <div className={`p-3.5 rounded-2xl w-fit mb-4 transition-colors ${strategy === strat.id ? `bg-gradient-to-br ${strat.gradient} text-white shadow-lg` : strat.bgLight}`}>
                  {strat.icon}
                </div>
                <h3 className="text-xl font-bold text-slate-900 mb-1">{strat.label}</h3>
                <p className="text-slate-500 text-sm">{strat.desc}</p>
              </div>
            </button>
          ))}
        </div>

        {/* Stock List Card */}
        <div className="bg-white rounded-3xl shadow-sm border border-slate-100 overflow-hidden">
          <div className="px-8 py-6 border-b border-slate-100 flex items-center justify-between bg-slate-50/50">
            <h2 className="text-xl font-bold flex items-center gap-3 text-slate-900">
              <TrendingUp className="text-indigo-500" />
              Top Picks สำหรับคุณ
            </h2>
            <span className="text-sm font-medium text-slate-500 bg-white px-3 py-1 rounded-full border border-slate-200">
              {picks.length} หุ้นแนะนำ
            </span>
          </div>

          {loading ? (
            <div className="py-24 text-center">
              <div className="relative w-16 h-16 mx-auto mb-6">
                <div className="absolute inset-0 border-4 border-indigo-100 rounded-full"></div>
                <div className="absolute inset-0 border-4 border-indigo-500 rounded-full border-t-transparent animate-spin"></div>
                <Bot className="absolute inset-0 m-auto text-indigo-500 w-6 h-6 animate-pulse" />
              </div>
              <h3 className="text-lg font-bold text-slate-800 mb-1">AI กำลังประมวลผล</h3>
              <p className="text-slate-500 text-sm">วิเคราะห์ข้อมูลย้อนหลังและข่าวสารล่าสุด...</p>
            </div>
          ) : (
            <div className="divide-y divide-slate-100">
              {picks.map((pick, idx) => (
                <div key={idx} className="hover:bg-slate-50/50 transition-colors">
                  {(() => {
                    const assetMeta = inferAssetMeta({
                      symbol: pick.symbol,
                      name: pick.name,
                    });

                    return (
                  <div className="p-8 flex flex-col lg:flex-row items-center gap-6 lg:gap-8">
                    
                    {/* Score Circle */}
                    <div className="relative group shrink-0">
                      <svg className="w-24 h-24 transform -rotate-90">
                        <circle cx="48" cy="48" r="40" stroke="currentColor" strokeWidth="6" fill="transparent" className="text-slate-100" />
                        <circle cx="48" cy="48" r="40" stroke="currentColor" strokeWidth="6" fill="transparent" 
                          strokeDasharray={251.2} strokeDashoffset={251.2 - (251.2 * pick.ai_score) / 100}
                          className="text-indigo-500 transition-all duration-1000 ease-out" 
                        />
                      </svg>
                      <div className="absolute inset-0 flex flex-col items-center justify-center">
                        <span className="text-2xl font-black text-slate-800">{pick.ai_score}</span>
                        <span className="text-[10px] uppercase font-bold text-slate-400">Score</span>
                      </div>
                    </div>

                    {/* Stock Details */}
                    <div className="flex-1 text-center lg:text-left">
                      <div className="flex flex-col lg:flex-row lg:items-end gap-2 lg:gap-4 mb-3">
                        <div className="flex flex-wrap items-center justify-center lg:justify-start gap-2">
                          <h3 className="text-3xl font-black text-slate-900">{pick.symbol}</h3>
                          {assetMeta.isEtf ? (
                            <span
                              title={assetMeta.assetTypeDescription || undefined}
                              className={`${assetMeta.badgeClass} inline-flex shrink-0 items-center rounded-full border px-2 py-0.5 text-[10px] font-black uppercase tracking-wide cursor-help`}
                            >
                              {assetMeta.badgeLabel || "ETF"}
                            </span>
                          ) : null}
                        </div>
                        <span className="text-slate-500 font-medium mb-1">{assetMeta.isEtf ? assetMeta.displayName : pick.name}</span>
                        {assetMeta.isEtf ? (
                          <span className="text-xs font-bold text-slate-400 uppercase tracking-wide mb-1">{assetMeta.assetType}</span>
                        ) : null}
                      </div>
                      
                      <div className="flex flex-wrap items-center justify-center lg:justify-start gap-3">
                        <span className="bg-emerald-50 text-emerald-700 text-sm font-semibold px-4 py-1.5 rounded-full flex items-center gap-1.5 border border-emerald-100">
                          <CheckCircle2 size={16} /> {pick.reason}
                        </span>
                        
                        <button 
                          onClick={() => analyzeStockDeeply(pick)}
                          className={`text-sm font-bold px-4 py-1.5 rounded-full border transition-all flex items-center gap-1.5
                            ${analysisId === pick.symbol 
                              ? 'bg-slate-900 text-white border-slate-900 shadow-md' 
                              : 'text-indigo-600 border-indigo-200 hover:bg-indigo-50 hover:border-indigo-300'}
                          `}
                        >
                          <Sparkles size={14} className={analysisId === pick.symbol ? 'text-yellow-300' : ''} /> 
                          {analysisId === pick.symbol ? 'ซ่อนการวิเคราะห์' : 'ให้ AI วิเคราะห์ลึก'}
                        </button>
                      </div>
                    </div>

                    {/* Price & Metrics */}
                    <div className="grid grid-cols-2 gap-8 text-right bg-white p-4 rounded-2xl border border-slate-100 shadow-sm w-full lg:w-auto">
                      <div>
                        <p className="text-xs text-slate-400 uppercase font-bold tracking-wider mb-1">Current Price</p>
                        <p className="font-mono text-2xl font-bold text-slate-800">${pick.latest_price?.toFixed(2)}</p>
                      </div>
                      <div>
                        <p className="text-xs text-slate-400 uppercase font-bold tracking-wider mb-1">30D Return</p>
                        <div className={`inline-flex items-center gap-1 px-2 py-1 rounded-lg font-mono text-xl font-bold
                          ${pick.ret30 >= 0 ? 'text-emerald-600 bg-emerald-50' : 'text-rose-600 bg-rose-50'}`}>
                          {pick.ret30 > 0 ? '+' : ''}{pick.ret30}%
                        </div>
                      </div>
                    </div>
                  </div>
                    );
                  })()}

                  {/* Deep Analysis Expandable Area */}
                  {analysisId === pick.symbol && (
                    <div className="px-8 pb-8 animate-in slide-in-from-top-4 duration-300">
                      <div className="bg-gradient-to-r from-slate-50 to-indigo-50/30 p-6 rounded-2xl border border-indigo-100 relative">
                        {!detailedAnalysis[pick.symbol] ? (
                          <div className="flex items-center gap-3 text-slate-600 font-medium">
                            <Loader2 className="w-5 h-5 animate-spin text-indigo-500" />
                            กำลังอ่านกราฟและดึงข้อมูลงบการเงิน...
                          </div>
                        ) : (
                          <div className="flex gap-4">
                            <div className="mt-1">
                              <Sparkles className="w-6 h-6 text-indigo-500" />
                            </div>
                            <div>
                              <h5 className="font-bold text-slate-900 mb-2">บทวิเคราะห์จาก AI</h5>
                              <p className="text-slate-700 leading-relaxed">
                                {detailedAnalysis[pick.symbol]}
                              </p>
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Chat Section */}
        <div className="bg-white p-8 rounded-3xl border border-slate-200 shadow-xl shadow-slate-200/50 relative overflow-hidden">
          <div className="absolute top-0 right-0 w-64 h-64 bg-gradient-to-br from-indigo-100 to-purple-100 rounded-full blur-3xl opacity-50 -mr-20 -mt-20 pointer-events-none"></div>
          
          <div className="relative z-10">
            <h3 className="text-2xl font-bold text-slate-900 flex items-center gap-3 mb-6">
              <MessageSquare className="text-indigo-500" />
              ปรึกษาพอร์ตกับ Gemini
            </h3>
            
            <form onSubmit={askCustomQuestion} className="relative group">
              <input 
                type="text" 
                value={customQuestion}
                onChange={(e) => setCustomQuestion(e.target.value)}
                placeholder="พิมพ์ถามได้เลย เช่น หุ้นกลุ่มไหนน่าซื้อเก็บยาวๆ? หรือ ช่วยจัดพอร์ตให้หน่อย..." 
                className="w-full pl-6 pr-16 py-5 rounded-2xl border-2 border-slate-200 bg-slate-50 text-slate-800 text-lg focus:outline-none focus:border-indigo-500 focus:bg-white transition-all shadow-inner"
              />
              <button 
                type="submit" 
                disabled={chatLoading || !customQuestion.trim()}
                className="absolute right-3 top-3 bottom-3 aspect-square bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl flex items-center justify-center transition-all disabled:opacity-50 disabled:hover:bg-indigo-600 group-focus-within:shadow-lg group-focus-within:shadow-indigo-500/30"
              >
                {chatLoading ? <Loader2 className="w-6 h-6 animate-spin" /> : <ArrowRight className="w-6 h-6" />}
              </button>
            </form>

            {chatResponse && (
              <div className="mt-6 flex gap-4 animate-in fade-in slide-in-from-bottom-4 duration-500">
                <div className="w-10 h-10 rounded-full bg-gradient-to-br from-indigo-500 to-purple-500 flex items-center justify-center shrink-0 shadow-lg shadow-indigo-500/30">
                  <Bot className="w-6 h-6 text-white" />
                </div>
                <div className="bg-slate-100 text-slate-800 px-6 py-4 rounded-2xl rounded-tl-sm text-lg leading-relaxed shadow-sm">
                  {chatResponse}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Footer Note */}
        <div className="flex items-center justify-center gap-2 text-slate-400 text-sm pb-8">
          <AlertCircle size={14} />
          ข้อมูลนี้สร้างโดย AI (Gemini) ควรใช้เพื่อประกอบการตัดสินใจเท่านั้น
        </div>
        
      </div>
    </div>
  );
}
