function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== "") {
        const cookies = document.cookie.split(";");
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === name + "=") {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}


function checkStatus() {
    const statusUrl = document.getElementById("queue-meta").dataset.statusUrl;
    const username = document.getElementById("queue-meta").dataset.username;
    const boardSize = document.getElementById("queue-meta").dataset.boardSize;
    const skillLevel = document.getElementById("queue-meta").dataset.skillLevel;
    const csrftoken = getCookie("csrftoken");

    fetch(statusUrl, {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded", "X-CSRFToken": csrftoken },
        body: new URLSearchParams({ board_size: boardSize, skill_level: skillLevel })
    })
        .then(response => {
            if (response.redirected) {
                window.location.href = response.url;
                return;
            }
            return response.text();
        })
        .then(html => {
            if (html) {
                document.querySelector(".queue-wrap").innerHTML = html;
                setTimeout(checkStatus, 3000);
            }
        })
        .catch(() => setTimeout(checkStatus, 5000));
}

setTimeout(checkStatus, 2000);
