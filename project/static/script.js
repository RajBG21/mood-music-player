// ---------------------------------------------
// Fade-in animation for all pages
// ---------------------------------------------
document.addEventListener("DOMContentLoaded", () => {
    document.body.classList.add("fade-in");
});

// ---------------------------------------------
// Auto-hide flash messages
// ---------------------------------------------
setTimeout(() => {
    const flash = document.querySelector(".flash-message");
    if (flash) {
        flash.style.opacity = "0";
        setTimeout(() => flash.remove(), 500);
    }
}, 3000);

// ---------------------------------------------
// Add active visual effect to mood buttons
// ---------------------------------------------
const moodButtons = document.querySelectorAll(".mood-btn");

moodButtons.forEach(btn => {
    btn.addEventListener("click", () => {
        moodButtons.forEach(b => b.classList.remove("active-mood"));
        btn.classList.add("active-mood");
    });
});

// ---------------------------------------------
// Show a loading message when navigating to playlist
// ---------------------------------------------
const playlistLinks = document.querySelectorAll("a[href*='playlist']");

playlistLinks.forEach(link => {
    link.addEventListener("click", (event) => {
        // Prevent showing loader when middle-click or ctrl-clicking
        if (event.ctrlKey || event.metaKey || event.button === 1) return;

        const loader = document.createElement("div");
        loader.id = "loading";
        loader.innerHTML = `
            <div class="loading-spinner"></div>
            <p>Fetching your playlist...</p>
        `;
        document.body.appendChild(loader);
    });
});


// ---------------------------------------------
// Optional: Dark mode toggle support
// (Only active if you add a button with id="theme-toggle")
// ---------------------------------------------
const toggle = document.getElementById("theme-toggle");

if (toggle) {
    toggle.addEventListener("click", () => {
        document.body.classList.toggle("dark-mode");
        localStorage.setItem("theme",
            document.body.classList.contains("dark-mode") ? "dark" : "light"
        );
    });

    // Load saved theme
    if (localStorage.getItem("theme") === "dark") {
        document.body.classList.add("dark-mode");
    }
}

window.addEventListener("pageshow", (event) => {
    if (event.persisted) {
        // If page was loaded from cache, remove loader
        const loader = document.getElementById("loading");
        if (loader) loader.remove();
    }
});
