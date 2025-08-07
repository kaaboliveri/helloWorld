// Initialize the map and set its view to our chosen geographical coordinates and zoom level
var map = L.map('map').setView([48.9, 4.5], 6);

// Add a tile layer to add to our map
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: 'Map data &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    maxZoom: 18,
}).addTo(map);

// Add a marker for Paris
L.marker([48.8566, 2.3522]).addTo(map)
    .bindPopup('Paris');

// Add a marker for Brussels
L.marker([50.8503, 4.3517]).addTo(map)
    .bindPopup('Bruxelles');
