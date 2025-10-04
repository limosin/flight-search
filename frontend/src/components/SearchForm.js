import React, { useState } from 'react';
import './SearchForm.css';

const SearchForm = ({ onSearch, loading }) => {
  const [formData, setFormData] = useState({
    origin: 'DEL',
    destination: 'BLR',
    date: '2025-10-10',
    passengers: 1,
    cabin: 'economy',
    max_hops: 2,
    max_results: 50,
    sort: 'price'
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

  const handleSubmit = (e) => {
    e.preventDefault();
    onSearch(formData);
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

        <div className="form-group">
          <label htmlFor="max_hops">Maximum Stops</label>
          <select
            id="max_hops"
            name="max_hops"
            value={formData.max_hops}
            onChange={handleChange}
          >
            <option value="0">Direct (0 stops)</option>
            <option value="1">1 stop</option>
            <option value="2">2 stops</option>
          </select>
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
            max="100"
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
