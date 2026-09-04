/** @odoo-module **/

function saveGuestLocation(latitude, longitude) {
    try {
        fetch("/mst_advanced_login_history/save_guest_location", {
            method: "POST",
            credentials: "same-origin",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({
                latitude: latitude,
                longitude: longitude,
            }),
        }).catch(function (error) {
            console.log("Guest location save failed", error);
        });
    } catch (error) {
        console.log("Guest location error", error);
    }
}

function askLoginPageLocation() {
    try {
        if (!navigator.geolocation) {
            return;
        }

        const isLocalhost = [
            "localhost",
            "127.0.0.1",
            "::1",
        ].includes(window.location.hostname);

        if (!window.isSecureContext && !isLocalhost) {
            console.log("Location requires HTTPS or localhost.");
            return;
        }

        navigator.geolocation.getCurrentPosition(
            function (position) {
                saveGuestLocation(
                    position.coords.latitude,
                    position.coords.longitude
                );
            },
            function (error) {
                console.log("Login page location denied or failed", error);
            },
            {
                enableHighAccuracy: true,
                timeout: 10000,
                maximumAge: 0,
            }
        );
    } catch (error) {
        console.log("Login page location tracking failed", error);
    }
}

setTimeout(function () {
    askLoginPageLocation();
}, 800);