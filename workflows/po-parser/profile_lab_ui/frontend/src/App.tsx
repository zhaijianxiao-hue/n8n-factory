import { Activity, AlertTriangle, Database, Loader2 } from "lucide-react";
import { useEffect, useState } from "react";

import { api } from "./api";
import type { CustomerSummary } from "./types";

type LoadState = "loading" | "ready" | "error";

export default function App() {
  const [customers, setCustomers] = useState<CustomerSummary[]>([]);
  const [state, setState] = useState<LoadState>("loading");
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;

    api
      .customers()
      .then((rows) => {
        if (cancelled) {
          return;
        }
        setCustomers(rows);
        setState("ready");
      })
      .catch((err: unknown) => {
        if (cancelled) {
          return;
        }
        setError(err instanceof Error ? err.message : "无法加载客户列表");
        setState("error");
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const runCount = customers.reduce((total, customer) => total + customer.run_count, 0);

  return (
    <main className="app-shell">
      <section className="console">
        <header className="console-header">
          <div>
            <p className="eyebrow">PROFILE CONTROL</p>
            <h1>PO Profile Lab</h1>
          </div>
          <div className={`status-pill status-${state}`}>
            {state === "loading" ? <Loader2 size={16} className="spin" /> : null}
            {state === "ready" ? <Activity size={16} /> : null}
            {state === "error" ? <AlertTriangle size={16} /> : null}
            <span>{state === "loading" ? "SYNCING" : state === "ready" ? "ONLINE" : "CHECK API"}</span>
          </div>
        </header>

        <div className="meter-grid">
          <article className="metric-panel">
            <Database size={22} />
            <span>Customers</span>
            <strong>{state === "loading" ? "--" : customers.length}</strong>
          </article>
          <article className="metric-panel">
            <Activity size={22} />
            <span>Runs</span>
            <strong>{state === "loading" ? "--" : runCount}</strong>
          </article>
        </div>

        <section className="feed-panel" aria-live="polite">
          {state === "loading" ? (
            <div className="feed-row">
              <Loader2 size={18} className="spin" />
              <span>正在读取客户 profile 资产...</span>
            </div>
          ) : null}

          {state === "error" ? (
            <div className="feed-row error-row">
              <AlertTriangle size={18} />
              <span>{error}</span>
            </div>
          ) : null}

          {state === "ready" ? (
            <>
              <div className="feed-row">
                <Activity size={18} />
                <span>已连接 API，发现 {customers.length} 个客户。</span>
              </div>
              <div className="customer-list">
                {customers.map((customer) => (
                  <div className="customer-row" key={customer.customer_key}>
                    <div>
                      <strong>{customer.display_name}</strong>
                      <span>{customer.customer_key}</span>
                    </div>
                    <b>{customer.run_count}</b>
                  </div>
                ))}
              </div>
            </>
          ) : null}
        </section>
      </section>
    </main>
  );
}
