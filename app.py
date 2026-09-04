
import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime
from supabase import create_client, Client

st.set_page_config(
    page_title="Cartera Borsa",
    page_icon="📈",
    layout="wide",
)

# ---------------------------
# ESTIL
# ---------------------------
st.markdown("""
<style>
    .block-container {
        padding-top: 1.2rem;
        padding-bottom: 1rem;
        max-width: 1250px;
    }
    [data-testid="stMetricValue"] {
        font-size: 1.55rem;
    }
    div[data-testid="stDataFrame"] {
        border: 1px solid #e9e9e9;
        border-radius: 10px;
    }
</style>
""", unsafe_allow_html=True)

# ---------------------------
# SUPABASE
# ---------------------------
@st.cache_resource
def get_supabase():
    try:
        url = st.secrets["supabase"]["url"]
        key = st.secrets["supabase"]["key"]
        return create_client(url, key)
    except Exception:
        return None

supabase: Client | None = get_supabase()

# ---------------------------
# HELPERS
# ---------------------------
def eur(value):
    if value is None or pd.isna(value):
        return "—"
    return f"{value:,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")

def pct(value):
    if value is None or pd.isna(value):
        return "—"
    return f"{value:+.2f}%".replace(".", ",")

@st.cache_data(ttl=300, show_spinner=False)
def get_quote(ticker: str):
    try:
        tk = yf.Ticker(ticker)
        hist = tk.history(period="1y", auto_adjust=False, actions=True)

        if hist.empty or "Close" not in hist.columns:
            return None

        closes = hist["Close"].dropna()
        if closes.empty:
            return None

        current = float(closes.iloc[-1])
        previous = float(closes.iloc[-2]) if len(closes) > 1 else current
        change = current - previous
        change_pct = (change / previous * 100) if previous else None

        dividend_rate = None
        if "Dividends" in hist.columns:
            dividends = hist["Dividends"].dropna()
            if not dividends.empty:
                dividend_rate = float(dividends.sum())
                if dividend_rate == 0:
                    dividend_rate = None

        metadata = getattr(tk, "history_metadata", {}) or {}
        currency = metadata.get("currency")

        dividend_yield = (
            dividend_rate / current * 100
            if dividend_rate is not None and current
            else None
        )

        return {
            "current_price": current,
            "previous_close": previous,
            "day_change": change,
            "day_change_pct": change_pct,
            "currency": currency,
            "dividend_rate": dividend_rate,
            "dividend_yield": dividend_yield,
        }
    except Exception:
        return None

def load_positions():
    if supabase is None:
        return []
    try:
        res = supabase.table("cartera_valors").select("*").order("nom").execute()
        return res.data or []
    except Exception as e:
        st.error(f"No s'han pogut carregar les dades de Supabase: {e}")
        return []

def add_position(data):
    if supabase is None:
        return False, "Supabase no està configurat."
    try:
        supabase.table("cartera_valors").insert(data).execute()
        return True, None
    except Exception as e:
        return False, str(e)

def update_position(row_id, data):
    if supabase is None:
        return False, "Supabase no està configurat."
    try:
        supabase.table("cartera_valors").update(data).eq("id", row_id).execute()
        return True, None
    except Exception as e:
        return False, str(e)

def delete_position(row_id):
    if supabase is None:
        return False, "Supabase no està configurat."
    try:
        supabase.table("cartera_valors").delete().eq("id", row_id).execute()
        return True, None
    except Exception as e:
        return False, str(e)

def save_portfolio_summary(total_value, total_invested, total_pl, annual_div):
    if supabase is None:
        return False, "Supabase no està configurat."

    try:
        now = datetime.utcnow()

        payload = {
            "data": now.date().isoformat(),
            "valor_actual": float(total_value),
            "invertit": float(total_invested),
            "resultat": float(total_pl),
            "dividend_anual": 0.0 if pd.isna(annual_div) else float(annual_div),
            "updated_at": now.isoformat(),
        }

        supabase.table("cartera_resum").upsert(
            payload,
            on_conflict="data",
        ).execute()

        return True, None

    except Exception as e:
        return False, str(e)

# ---------------------------
# CAPÇALERA
# ---------------------------
c1, c2 = st.columns([4, 1])
with c1:
    st.title("📈 Cartera de valors")
    st.caption("Seguiment automàtic de cotitzacions, rendibilitat, dividends i radar.")
with c2:
    if st.button("🔄 Actualitzar ara", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

if supabase is None:
    st.warning(
        "Supabase encara no està configurat. "
        "Afegeix URL i KEY a `.streamlit/secrets.toml` per guardar la cartera."
    )

# ---------------------------
# CARREGA I COTITZACIONS
# ---------------------------
positions = load_positions()
eurusd_quote = get_quote("EURUSD=X")
eurusd_rate = (
    eurusd_quote["current_price"]
    if eurusd_quote and eurusd_quote.get("current_price")
    else None
)
rows = []
for p in positions:
    q = get_quote(p["ticker"])
    current = q["current_price"] if q else None
    shares = float(p.get("accions") or 0)
    avg_price = float(p.get("preu_mitja") or 0)
    currency = q.get("currency") if q else None
    if currency is None:
        euro_suffixes = (".MC", ".DE", ".MI", ".AS")
        currency = "EUR" if p["ticker"].endswith(euro_suffixes) else "USD"

    fx_to_eur = 1.0
    if currency == "USD":
        fx_to_eur = 1 / eurusd_rate if eurusd_rate else None

    if fx_to_eur is None:
        current = None
    else:
        current = current * fx_to_eur if current is not None else None
        avg_price = avg_price * fx_to_eur
    invested = shares * avg_price
    current_value = shares * current if current is not None else None
    total_pl = current_value - invested if current_value is not None else None
    total_pl_pct = (total_pl / invested * 100) if invested else None
    day_pl = (
        shares * q["day_change"] * fx_to_eur
        if q and q["day_change"] is not None and fx_to_eur is not None
        else None
    )

    dividend_rate = q.get("dividend_rate") if q else None
    if dividend_rate is not None and fx_to_eur is not None:
        dividend_rate = dividend_rate * fx_to_eur
    else:
        dividend_rate = None

    annual_dividend = (
        shares * dividend_rate if dividend_rate is not None else None
    )

    rows.append({
        "id": p["id"],
        "Nom": p["nom"],
        "Ticker": p["ticker"],
        "Accions": shares,
        "Preu mitjà": avg_price,
        "Cotització": current,
        "Valor actual": current_value,
        "Invertit": invested,
        "Guany/Pèrdua": total_pl,
        "Rendibilitat %": total_pl_pct,
        "Canvi dia %": q["day_change_pct"] if q else None,
        "Guany/Pèrdua dia": day_pl,
        "Dividend/acció": dividend_rate,
        "Dividend anual estimat": annual_dividend,
        "Radar": p.get("radar") or "🟡 Vigilar",
        "Notes": p.get("notes") or "",
    })

df = pd.DataFrame(rows)

# ---------------------------
# RESUM
# ---------------------------
if not df.empty:
    valid_df = df[df["Valor actual"].notna()].copy()
    missing_quotes = int(df["Valor actual"].isna().sum())

    total_value = valid_df["Valor actual"].sum(min_count=1)
    total_invested = valid_df["Invertit"].sum(min_count=1)
    total_pl = total_value - total_invested
    total_pl_pct = total_pl / total_invested * 100 if total_invested else 0
    day_pl = valid_df["Guany/Pèrdua dia"].sum(min_count=1)
    annual_div = valid_df["Dividend anual estimat"].sum(min_count=1)
    summary_error = None

    _, summary_error = save_portfolio_summary(
        total_value,
        total_invested,
        total_pl,
        annual_div,
    )

    if summary_error:
        st.warning(
            f"No s'ha pogut sincronitzar el resum de la cartera: {summary_error}"
        )

    if missing_quotes:
        st.warning(
            f"⚠️ Falten {missing_quotes} cotitzacions. Els totals mostrats són parcials."
        )

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Valor actual", eur(total_value))
    m2.metric("Resultat acumulat", eur(total_pl), pct(total_pl_pct))
    m3.metric("Resultat del dia", eur(day_pl))
    m4.metric("Dividend anual estimat", eur(annual_div))

    st.divider()

    display_df = df[[
        "Nom", "Ticker", "Accions", "Cotització", "Valor actual",
        "Canvi dia %", "Guany/Pèrdua", "Rendibilitat %",
        "Dividend anual estimat", "Radar"
    ]].copy()

    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Accions": st.column_config.NumberColumn(format="%.2f"),
            "Cotització": st.column_config.NumberColumn(format="%.2f €"),
            "Valor actual": st.column_config.NumberColumn(format="%.2f €"),
            "Canvi dia %": st.column_config.NumberColumn(format="%+.2f %%"),
            "Guany/Pèrdua": st.column_config.NumberColumn(format="%.2f €"),
            "Rendibilitat %": st.column_config.NumberColumn(format="%+.2f %%"),
            "Dividend anual estimat": st.column_config.NumberColumn(format="%.2f €"),
        }
    )
else:
    st.info("Encara no hi ha cap valor a la cartera.")

# ---------------------------
# GESTIÓ
# ---------------------------
tab1, tab2, tab3 = st.tabs(["➕ Afegir valor", "✏️ Editar", "🗑️ Eliminar"])

with tab1:
    with st.form("add_value", clear_on_submit=True):
        a, b = st.columns(2)
        with a:
            nom = st.text_input("Nom", placeholder="Ex.: Endesa")
            ticker = st.text_input(
                "Ticker Yahoo Finance",
                placeholder="Ex.: ELE.MC",
                help="Per valors espanyols normalment s'utilitza .MC"
            ).upper().strip()
            accions = st.number_input("Nombre d'accions", min_value=0.0, step=1.0)
        with b:
            preu_mitja = st.number_input("Preu mitjà de compra", min_value=0.0, step=0.01)
            radar = st.selectbox(
                "Radar",
                ["🟢 Mantenir", "🟡 Vigilar", "🔴 Revisar"]
            )
            notes = st.text_area("Notes")

        submitted = st.form_submit_button("💾 Guardar valor", use_container_width=True)

        if submitted:
            if not nom or not ticker:
                st.error("Nom i ticker són obligatoris.")
            else:
                ok, err = add_position({
                    "nom": nom.strip(),
                    "ticker": ticker,
                    "accions": float(accions),
                    "preu_mitja": float(preu_mitja),
                    "radar": radar,
                    "notes": notes.strip(),
                })
                if ok:
                    st.success("Valor guardat.")
                    st.cache_data.clear()
                    st.rerun()
                else:
                    st.error(err)

with tab2:
    if positions:
        options = {f'{p["nom"]} · {p["ticker"]}': p for p in positions}
        selected_label = st.selectbox("Valor a editar", options.keys())
        selected = options[selected_label]

        with st.form("edit_value"):
            a, b = st.columns(2)
            with a:
                e_nom = st.text_input("Nom", value=selected["nom"])
                e_ticker = st.text_input("Ticker", value=selected["ticker"]).upper().strip()
                e_accions = st.number_input(
                    "Nombre d'accions",
                    min_value=0.0,
                    step=1.0,
                    value=float(selected.get("accions") or 0)
                )
            with b:
                e_preu = st.number_input(
                    "Preu mitjà de compra",
                    min_value=0.0,
                    step=0.01,
                    value=float(selected.get("preu_mitja") or 0)
                )
                radar_options = ["🟢 Mantenir", "🟡 Vigilar", "🔴 Revisar"]
                current_radar = selected.get("radar") or "🟡 Vigilar"
                idx = radar_options.index(current_radar) if current_radar in radar_options else 1
                e_radar = st.selectbox("Radar", radar_options, index=idx)
                e_notes = st.text_area("Notes", value=selected.get("notes") or "")

            save_edit = st.form_submit_button("💾 Guardar canvis", use_container_width=True)

            if save_edit:
                ok, err = update_position(selected["id"], {
                    "nom": e_nom.strip(),
                    "ticker": e_ticker,
                    "accions": float(e_accions),
                    "preu_mitja": float(e_preu),
                    "radar": e_radar,
                    "notes": e_notes.strip(),
                    "updated_at": datetime.utcnow().isoformat(),
                })
                if ok:
                    st.success("Canvis guardats.")
                    st.cache_data.clear()
                    st.rerun()
                else:
                    st.error(err)
    else:
        st.info("No hi ha valors per editar.")

with tab3:
    if positions:
        delete_options = {f'{p["nom"]} · {p["ticker"]}': p for p in positions}
        delete_label = st.selectbox("Valor a eliminar", delete_options.keys(), key="delete_select")
        delete_sel = delete_options[delete_label]
        st.warning("Aquesta acció elimina el valor de la cartera.")
        confirm = st.checkbox("Confirmo que vull eliminar-lo")
        if st.button("🗑️ Eliminar definitivament", disabled=not confirm):
            ok, err = delete_position(delete_sel["id"])
            if ok:
                st.success("Valor eliminat.")
                st.cache_data.clear()
                st.rerun()
            else:
                st.error(err)
    else:
        st.info("No hi ha valors per eliminar.")

st.caption(
    "Cotitzacions obtingudes automàticament. "
    "Les dades de mercat poden tenir retard segons la font."
)
