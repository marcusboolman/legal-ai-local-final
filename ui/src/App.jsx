import React, {useEffect, useState} from "react";

export default function App(){
  const [caseId, setCaseId] = useState("sample_case_001");
  const [question, setQuestion] = useState("本案争议焦点为何？");
  const [answer, setAnswer] = useState(null);
  const [chunks, setChunks] = useState([]);
  const [assets, setAssets] = useState([]);
  const [selectedAsset, setSelectedAsset] = useState(null);

  async function ask(){
    setAnswer("检索中...");
    const resp = await fetch("/qa/ask", {
      method: "POST", headers: {"Content-Type":"application/json"},
      body: JSON.stringify({case_id: caseId, question: question})
    });
    const j = await resp.json();
    setAnswer(j.answer);
    setChunks(j.citations || []);
  }

  async function loadAssets(){
    const r = await fetch(`/case/${caseId}/assets/list`);
    const j = await r.json();
    setAssets(j.assets || []);
  }

  useEffect(()=>{ loadAssets(); }, [caseId]);

  function selectAsset(a){
    setSelectedAsset(a);
  }

  return (
    <div style={{padding:20,fontFamily:"Arial"}}>
      <h2>案件问答与证据可视化（演示）</h2>
      <div style={{marginBottom:10}}>
        <label>Case ID: <input value={caseId} onChange={e=>setCaseId(e.target.value)} /></label>
        <button onClick={loadAssets} style={{marginLeft:10}}>刷新资产</button>
      </div>
      <div style={{marginBottom:10}}>
        <textarea rows={4} cols={80} value={question} onChange={e=>setQuestion(e.target.value)} />
      </div>
      <button onClick={ask}>提问</button>
      <h3>答案</h3>
      <pre style={{whiteSpace:"pre-wrap",background:"#f6f6f6",padding:10}}>{answer}</pre>
      <h3>检索到的引用片段</h3>
      <ul>
        {chunks.map(c=>(<li key={c.chunk_id}>{c.chunk_id} — {c.asset} p.{c.page}</li>))}
      </ul>

      <h3>案件资产</h3>
      <div style={{display:"flex",gap:20}}>
        <div style={{minWidth:300}}>
          <ul>
            {assets.map(a=>(
              <li key={a.name}>
                <button onClick={()=>selectAsset(a)} style={{cursor:"pointer"}}>{a.name}</button>
              </li>
            ))}
          </ul>
        </div>
        <div style={{flex:1}}>
          {selectedAsset ? (
            <div>
              <h4>{selectedAsset.name}</h4>
              <div>
                {selectedAsset.name.match(/\.(mp4|mov|mkv|webm)$/i) ? (
                  <video src={selectedAsset.url} controls style={{maxWidth:"100%"}} />
                ) : selectedAsset.name.match(/\.(mp3|wav|m4a)$/i) ? (
                  <audio src={selectedAsset.url} controls />
                ) : (
                  <iframe src={selectedAsset.url} style={{width:"100%",height:600}} title={selectedAsset.name}></iframe>
                )}
              </div>
            </div>
          ) : <div>请选择一个资产以预览（视频/音频/文档）</div>}
        </div>
      </div>
    </div>
  )
}
