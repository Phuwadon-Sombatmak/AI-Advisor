import React, { useEffect, useState, useCallback } from "react";
import { useNavigate, Link } from "react-router-dom";
import { Star } from "lucide-react";
import "./FavoritePage.css";

const logoMap = {
  NVDA: "https://logo.clearbit.com/nvidia.com",
  MSFT: "https://logo.clearbit.com/microsoft.com",
  UNH:  "https://logo.clearbit.com/unitedhealthgroup.com",
  AMZN: "https://logo.clearbit.com/amazon.com",
  AMD:  "https://logo.clearbit.com/amd.com",
  GOOGL:"https://logo.clearbit.com/google.com",
  MU:   "https://logo.clearbit.com/micron.com",
  TSM:  "https://logo.clearbit.com/taiwansemiconductor.com",
  NVO:  "https://logo.clearbit.com/novonordisk.com",
  META: "https://logo.clearbit.com/meta.com",
  BRK: "https://logo.clearbit.com/berkshirehathaway.com",
};

export default function Favorite() {
  const navigate = useNavigate();
  const [favorites, setFavorites] = useState([]);
  const [stocks, setStocks] = useState([]);
  const [loading, setLoading] = useState(true);

  const getCompanyLogo = useCallback((symbol) => logoMap[symbol] || null, []);

  useEffect(() => {
  const stored = JSON.parse(localStorage.getItem("favorites")) || [];
  setFavorites(stored);

  if (!stored.length) {
    setLoading(false);
    return;
  }

  const symbolList = stored.map(s => s.trim().toUpperCase()).filter(Boolean);

  const fetchStocks = async () => {
    const stockPromises = symbolList.map(symbol =>
      fetch(`http://localhost:8000/stock/${symbol}`)
        .then(res => res.json())
        .then(stockData => ({
          symbol: stockData.symbol || stockData.ticker || symbol,
          name: stockData.name,
          price: stockData.price,
          logo: getCompanyLogo(symbol),
          news: [],
          averageRisk: 0,
        }))
        .catch(err => {
          console.error("Error fetching stock:", symbol, err);
          return null;
        })
    );

    const stockArray = (await Promise.all(stockPromises)).filter(Boolean);
    setStocks(stockArray); // render หุ้นทันที

    // fetch news ทีหลัง
    fetch(`http://localhost:8000/news?symbols=${symbolList.join(",")}`)
      .then(res => res.json())
      .then(newsData => {
        setStocks(prevStocks =>
          prevStocks.map(stock => {
            const newsObj = newsData.find(n => n.symbol === stock.symbol) || { news: [] };
            const averageRisk = newsObj.news.length > 0 
              ? newsObj.news.reduce((sum, item) => sum + (item.sentiment === "NEGATIVE" ? 1 : item.sentiment === "NEUTRAL" ? 0.5 : 0), 0) / newsObj.news.length
              : 0;
            return {
              ...stock,
              news: newsObj.news,
              averageRisk,
            };
          })
        );
      })
      .catch(err => console.error("Error fetching news:", err))
      .finally(() => setLoading(false));
  };

  fetchStocks();
}, [getCompanyLogo]);

  const removeFavorite = (symbol) => {
    const updatedFavorites = favorites.filter(
      (s) => typeof s === "string" && s.toUpperCase() !== symbol.toUpperCase()
    );
    const updatedStocks = stocks.filter(
      (s) => s.symbol && s.symbol.toUpperCase() !== symbol.toUpperCase()
    );

    localStorage.setItem("favorites", JSON.stringify(updatedFavorites));
    setFavorites(updatedFavorites);
    setStocks(updatedStocks);
  };

  const handleBack = () => navigate("/search"); // กลับไปหน้า dashboard

  return (
    <div className="favorite-page">
      <div className="back-button">
          <button
            onClick={handleBack} className="back-btn">
            Back
          </button>
        </div>

      <h2 className="text-3xl font-bold mb-6">Stocks to follow</h2>

       {loading ? (
        <p className="text-center">Loading...</p>
      ) : favorites.length === 0 ? (
        <p className="text-gray-600 text-center">There are no stocks you are following</p>
      ) : (
        <div className="favorite-card-container">
          {stocks.map((stock, index) => (
            <div key={stock.symbol || index} className="favorite-card">
              <Link
                to={`/stock/${stock.symbol}`}
                className="favorite-card-link"
              >
                <div className="favorite-card-left">
                  {stock.logo ? (
                    <img 
                      src={`https://financialmodelingprep.com/image-stock/${stock.symbol}.png`}
                      alt={stock.symbol}
                      className="stock-logo w-16 h-16 rounded-full object-contain bg-white p-1 border"
                      onError={(e) => {
                        e.target.onerror = null;
                        e.target.src = `https://via.placeholder.com/64/cccccc/ffffff?text=${stock.symbol}`;
                      }}
                    />
                  ) : (
                    <div className="favorite-placeholder">
                      {stock.symbol.charAt(0)}
                    </div>
                  )}
                </div>

                <div className="favorite-card-right">
                  <h3 className="favorite-symbol">{stock.symbol}</h3>
                  <span>{stock.name}</span>
                  <p className="favorite-price">
                    Latest price: <span>{stock.price}</span>
                  </p> 
                </div>
              </Link>

              {/* ⭐ ปุ่มเอาดาวออก */}
              <button
                className="unfavorite-btn"
                onClick={() => removeFavorite(stock.symbol)}
                title="Remove from favorites"
              >
                <Star fill="#facc15" stroke="#facc15" size={25} />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
