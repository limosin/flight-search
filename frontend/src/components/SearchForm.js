import React, { useState } from 'react';
import './SearchForm.css';

const SearchForm = ({ onSearch, loading }) => {
  const [formData, setFormData] = useState({
    origin: 'GOI',
    destination: 'COK',
    date: '2025-10-10',
    passengers: 1,
    cabin: 'economy',
    max_hops: 2,
    max_results: 200,
    sort: 'price'
  });

  const [stopFilters, setStopFilters] = useState({
    direct: true,
    oneStop: true,
    twoStops: true
  });

  const handleChange = (e) => {
    const { name, value } = e.target;
    
    setFormData(prev => ({
      ...prev,
      [name]: name === 'passengers' || name === 'max_hops' || name === 'max_results' 
        ? parseInt(value) 
        : value
    }));
  };

  const handleStopFilterChange = (e) => {
    const { name, checked } = e.target;
    setStopFilters(prev => ({
      ...prev,
      [name]: checked
    }));
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    onSearch({ ...formData, stopFilters });
  };

  return (
    <form className="search-form" onSubmit={handleSubmit}>
      <div className="form-grid">
        <div className="form-group">
          <label htmlFor="origin">Origin Airport Code</label>
          <input
            type="text"
            id="origin"
            name="origin"
            value={formData.origin}
            onChange={handleChange}
            placeholder="e.g., DEL"
            maxLength="3"
            required
          />
        </div>

        <div className="form-group">
          <label htmlFor="destination">Destination Airport Code</label>
          <input
            type="text"
            id="destination"
            name="destination"
            value={formData.destination}
            onChange={handleChange}
            placeholder="e.g., BLR"
            maxLength="3"
            required
          />
        </div>

        <div className="form-group">
          <label htmlFor="date">Travel Date</label>
          <input
            type="date"
            id="date"
            name="date"
            value={formData.date}
            onChange={handleChange}
            required
          />
        </div>

        <div className="form-group">
          <label htmlFor="passengers">Passengers</label>
          <input
            type="number"
            id="passengers"
            name="passengers"
            value={formData.passengers}
            onChange={handleChange}
            min="1"
            max="9"
            required
          />
        </div>

        <div className="form-group">
          <label htmlFor="cabin">Cabin Class</label>
          <select
            id="cabin"
            name="cabin"
            value={formData.cabin}
            onChange={handleChange}
          >
            <option value="economy">Economy</option>
            <option value="business">Business</option>
            <option value="first">First</option>
          </select>
        </div>

        <div className="form-group stops-filter">
          <label>Number of Stops</label>
          <div className="checkbox-group">
            <label className="checkbox-label">
              <input
                type="checkbox"
                name="direct"
                checked={stopFilters.direct}
                onChange={handleStopFilterChange}
              />
              <span>Direct</span>
            </label>
            <label className="checkbox-label">
              <input
                type="checkbox"
                name="oneStop"
                checked={stopFilters.oneStop}
                onChange={handleStopFilterChange}
              />
              <span>1 Stop</span>
            </label>
            <label className="checkbox-label">
              <input
                type="checkbox"
                name="twoStops"
                checked={stopFilters.twoStops}
                onChange={handleStopFilterChange}
              />
              <span>2 Stops</span>
            </label>
          </div>
        </div>

        <div className="form-group">
          <label htmlFor="sort">Sort By</label>
          <select
            id="sort"
            name="sort"
            value={formData.sort}
            onChange={handleChange}
          >
            <option value="price">Price</option>
            <option value="duration">Duration</option>
            <option value="departure_time">Departure Time</option>
          </select>
        </div>

        <div className="form-group">
          <label htmlFor="max_results">Max Results</label>
          <input
            type="number"
            id="max_results"
            name="max_results"
            value={formData.max_results}
            onChange={handleChange}
            min="1"
            max="200"
          />
        </div>
      </div>

      <button type="submit" className="search-button" disabled={loading}>
        {loading ? 'Searching...' : 'Search Flights'}
      </button>
    </form>
  );
};

export default SearchForm;
