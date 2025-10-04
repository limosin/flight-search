import React from 'react';
import './SearchResults.css';

const SearchResults = ({ results }) => {
  if (!results || !results.itineraries || results.itineraries.length === 0) {
    return (
      <div className="no-results">
        <h3>No flights found</h3>
        <p>Try adjusting your search criteria</p>
      </div>
    );
  }

  const formatTime = (utcTime) => {
    const date = new Date(utcTime);
    return date.toLocaleTimeString('en-US', { 
      hour: '2-digit', 
      minute: '2-digit',
      hour12: true 
    });
  };

  const formatDate = (utcTime) => {
    const date = new Date(utcTime);
    return date.toLocaleDateString('en-US', { 
      month: 'short', 
      day: 'numeric',
      year: 'numeric'
    });
  };

  const formatDuration = (minutes) => {
    const hours = Math.floor(minutes / 60);
    const mins = minutes % 60;
    return `${hours}h ${mins}m`;
  };

  const formatPrice = (price) => {
    return `${price.currency} ${price.amount.toLocaleString('en-IN', { 
      minimumFractionDigits: 2,
      maximumFractionDigits: 2 
    })}`;
  };

  return (
    <div className="search-results">
      <div className="results-header">
        <h2>Search Results</h2>
        <p className="results-count">
          Found {results.itineraries.length} flight{results.itineraries.length !== 1 ? 's' : ''}
        </p>
      </div>

      <div className="itineraries-list">
        {results.itineraries.map((itinerary) => (
          <div key={itinerary.id} className="itinerary-card">
            <div className="itinerary-header">
              <div className="stops-badge">
                {itinerary.stops === 0 ? 'Direct' : `${itinerary.stops} stop${itinerary.stops > 1 ? 's' : ''}`}
              </div>
              <div className="price">
                {formatPrice(itinerary.price)}
              </div>
            </div>

            <div className="itinerary-summary">
              <div className="summary-info">
                <div className="departure">
                  <div className="airport">{itinerary.legs[0].origin}</div>
                  <div className="time">{formatTime(itinerary.legs[0].departure_time_utc)}</div>
                  <div className="date">{formatDate(itinerary.legs[0].departure_time_utc)}</div>
                </div>
                
                <div className="journey-info">
                  <div className="duration">{formatDuration(itinerary.total_duration_minutes)}</div>
                  <div className="journey-line">
                    <div className="dot"></div>
                    <div className="line"></div>
                    <div className="dot"></div>
                  </div>
                </div>

                <div className="arrival">
                  <div className="airport">{itinerary.legs[itinerary.legs.length - 1].destination}</div>
                  <div className="time">{formatTime(itinerary.legs[itinerary.legs.length - 1].arrival_time_utc)}</div>
                  <div className="date">{formatDate(itinerary.legs[itinerary.legs.length - 1].arrival_time_utc)}</div>
                </div>
              </div>
            </div>

            <div className="legs-details">
              {itinerary.legs.map((leg, index) => (
                <div key={index} className="leg">
                  <div className="leg-header">
                    <span className="carrier">{leg.carrier} {leg.flight_number}</span>
                    <span className="leg-duration">{formatDuration(leg.duration_minutes)}</span>
                  </div>
                  <div className="leg-route">
                    <div className="leg-segment">
                      <strong>{leg.origin}</strong>
                      <span className="leg-time">{formatTime(leg.departure_time_utc)}</span>
                    </div>
                    <div className="leg-arrow">→</div>
                    <div className="leg-segment">
                      <strong>{leg.destination}</strong>
                      <span className="leg-time">{formatTime(leg.arrival_time_utc)}</span>
                    </div>
                  </div>
                  
                  {index < itinerary.legs.length - 1 && (
                    <div className="layover">
                      Layover at {leg.destination}
                    </div>
                  )}
                </div>
              ))}
            </div>

            <div className="itinerary-footer">
              <div className="fare-key">Fare Key: {itinerary.fare_key}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default SearchResults;
