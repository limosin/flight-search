import React, { useState } from 'react';
import './App.css';
import SearchForm from './components/SearchForm';
import SearchResults from './components/SearchResults';
import axios from 'axios';

function App() {
  const [searchResults, setSearchResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleSearch = async (searchParams) => {
    setLoading(true);
    setError(null);
    setSearchResults(null);

    try {
      // Separate stop filters from API params
      const { stopFilters, ...apiParams } = searchParams;
      
      const response = await axios.post('/v1/search', apiParams);
      
      // Filter results based on stop filters
      let filteredItineraries = response.data.itineraries || [];
      
      if (stopFilters) {
        filteredItineraries = filteredItineraries.filter(itinerary => {
          const stops = itinerary.stops;
          if (stops === 0 && stopFilters.direct) return true;
          if (stops === 1 && stopFilters.oneStop) return true;
          if (stops === 2 && stopFilters.twoStops) return true;
          return false;
        });
      }
      
      setSearchResults({
        ...response.data,
        itineraries: filteredItineraries
      });
    } catch (err) {
      setError(
        err.response?.data?.detail || 
        err.message || 
        'An error occurred while searching for flights'
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="App">
      <header className="App-header">
        <h1>✈️ Flight Search</h1>
        <p>Search for flights with up to 2 stops</p>
      </header>
      
      <main className="App-main">
        <SearchForm onSearch={handleSearch} loading={loading} />
        
        {loading && (
          <div className="loading">
            <div className="spinner"></div>
            <p>Searching for flights...</p>
          </div>
        )}
        
        {error && (
          <div className="error">
            <h3>Error</h3>
            <p>{error}</p>
          </div>
        )}
        
        {searchResults && !loading && (
          <SearchResults results={searchResults} />
        )}
      </main>
    </div>
  );
}

export default App;
