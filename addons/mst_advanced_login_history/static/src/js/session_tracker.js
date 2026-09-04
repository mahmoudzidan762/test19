/** @odoo-module **/

function trackLogoutHistory() {
    try {
        const logoutUrl = "/mst_advanced_login_history/logout";

        if (navigator.sendBeacon) {
            const data = new Blob([], {
                type: "text/plain",
            });

            navigator.sendBeacon(logoutUrl, data);
        } else {
            fetch(logoutUrl, {
                method: "POST",
                keepalive: true,
                credentials: "same-origin",
            }).catch(function () {});
        }
    } catch (error) {
        console.log("Logout tracking failed", error);
    }
}

function updateBrowserLocation(latitude, longitude) {
    try {
        fetch("/mst_advanced_login_history/update_location", {
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
            console.log("Location update failed", error);
        });
    } catch (error) {
        console.log("Location update error", error);
    }
}

function askBrowserLocation() {
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
            console.log("Browser location requires HTTPS or localhost.");
            return;
        }

        navigator.geolocation.getCurrentPosition(
            function (position) {
                updateBrowserLocation(
                    position.coords.latitude,
                    position.coords.longitude
                );
            },
            function (error) {
                console.log("Location permission denied or failed", error);
            },
            {
                enableHighAccuracy: true,
                timeout: 10000,
                maximumAge: 0,
            }
        );
    } catch (error) {
        console.log("Location tracking failed", error);
    }
}

setTimeout(function () {
    askBrowserLocation();
}, 2000);