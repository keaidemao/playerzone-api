const namesInput = document.getElementById('names');
const fetchButton = document.getElementById('fetchButton');
const resultsTable = document.getElementById('resultsTable').getElementsByTagName('tbody')[0];
const resultsSection = document.getElementById('results');

fetchButton.addEventListener('click', () => {
    const names = namesInput.value.trim().split('\n');
    resultsTable.innerHTML = ''; // Clear previous results
    resultsSection.style.display = 'none'; // Hide results until data is fetched

    const promises = names.map(name => {
        return fetch(`https://johanneskdl.pythonanywhere.com/elo/${encodeURIComponent(name)}`)
            .then(response => {
                if (!response.ok) {
                    throw new Error(`API request failed for ${name}`);
                }
                return response.json();
            })
            .catch(error => {
                console.error(error);
                return { name: name, error: 'Failed to fetch data' }; // Indicate error for the specific name
            });
    });

    Promise.all(promises)
        .then(results => {
            results.forEach(data => {
                const row = resultsTable.insertRow();
                const nameCell = row.insertCell();
                const eloCell = row.insertCell();
                const genderCell = row.insertCell();
                const matchScoreCell = row.insertCell();

                nameCell.textContent = data.name;

                if (data.error) {
                    eloCell.textContent = data.error;
                    genderCell.textContent = '';
                    matchScoreCell.textContent = '';
                } else {
                    eloCell.textContent = data.elo_rating;
                    genderCell.textContent = data.gender;
                    matchScoreCell.textContent = data.match_score;
                }
            });

            resultsSection.style.display = 'block'; // Show results after populating the table
        });
});