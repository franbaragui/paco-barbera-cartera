
# Cartera de valors

Primera versió de l'app de seguiment de cartera.

## Què fa
- Guarda la cartera a Supabase.
- Consulta cotitzacions automàticament amb Yahoo Finance via `yfinance`.
- Calcula valor actual, resultat acumulat i resultat del dia.
- Calcula una estimació del dividend anual quan la dada està disponible.
- Permet assignar un radar: 🟢 Mantenir / 🟡 Vigilar / 🔴 Revisar.
- Permet afegir, editar i eliminar valors.
- Botó `Actualitzar ara`.

## Fitxers
- `app.py` → aplicació Streamlit.
- `requirements.txt` → dependències.
- `supabase_schema.sql` → taula de Supabase.
- `.streamlit/secrets.toml.example` → plantilla de secrets.

## Tickers típics
Yahoo Finance utilitza sovint:
- Endesa: `ELE.MC`
- Atresmedia: `A3M.MC`
- Neinor Homes: `HOME.MC`
- Colonial: `COL.MC`
- Allianz: `ALV.DE`

Cal verificar el ticker exacte de cada valor abans d'afegir-lo.

## Següent fase prevista
- Històric de cartera.
- Dividends cobrats i previstos.
- Gràfics.
- Radar Alex amb preu objectiu, potencial i alertes.
- Importació inicial més ràpida de totes les posicions.
