// --- FIX: Αποτροπή μηνυμάτων σφάλματος [Intervention] για touch events στο Leaflet ---
const originalPreventDefault = Event.prototype.preventDefault;
Event.prototype.preventDefault = function() {
    if (this.cancelable !== false) {
        originalPreventDefault.call(this);
    }
};

// PWA Installation Logic
let deferredPrompt;
const installBtn = document.getElementById('installBtn');

if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/sw.js')
        .then(() => console.log('Service Worker Registered'));
}

window.addEventListener('beforeinstallprompt', (e) => {
    e.preventDefault();
    deferredPrompt = e;
    installBtn.style.display = 'block';
});

installBtn.addEventListener('click', async () => {
    if (deferredPrompt) {
        deferredPrompt.prompt();
        const { outcome } = await deferredPrompt.userChoice;
        console.log(`User response to the install prompt: ${outcome}`);
        deferredPrompt = null;
        installBtn.style.display = 'none';
    }
});

async function rwtaAI(id, temp, hum, desc, btn) {
    const divApantisis = document.getElementById('ai-apantisi-' + id);
    divApantisis.innerText = "Ο AI Γεωπόνος σκέφτεται...";
    
    // Απενεργοποίηση κουμπιού για αποφυγή spam
    if(btn) { btn.disabled = true; btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Φόρτωση...'; }
    
    try {
        const response = await fetch('/rwta_ai/' + id, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ thermokrasia: temp, ygrasia: hum, perigrafi: desc })
        });
        const data = await response.json();
        divApantisis.innerText = "🤖 " + data.apantisi;
    } catch (error) {
        divApantisis.innerText = "Σφάλμα επικοινωνίας με το AI.";
        console.error('Error:', error);
    } finally {
        // Επαναφορά κουμπιού μετά από 5 δευτερόλεπτα (Rate Limit Protection)
        if(btn) {
            setTimeout(() => { btn.disabled = false; btn.innerHTML = '<i class="fas fa-robot"></i> Ρώτα το AI'; }, 5000);
        }
    }
}

async function steileAnafora(onoma, temp, hum, id) {
    const divApantisis = document.getElementById('ai-apantisi-' + id);
    let aiText = divApantisis.innerText;
    
    // Αν δεν υπάρχει κείμενο AI, βάζουμε μια προεπιλογή
    if (!aiText || aiText === "") {
        aiText = "Δεν έχει ζητηθεί ακόμα συμβουλή από το AI.";
    }

    try {
        const response = await fetch('/steile_anafora', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                onoma_ktimatos: onoma,
                thermokrasia: temp,
                ygrasia: hum,
                ai_sumvouli: aiText
            })
        });
        
        if (response.ok) {
            alert('Η αναφορά στάλθηκε επιτυχώς στο email σας!');
        } else {
            alert('Υπήρξε πρόβλημα κατά την αποστολή.');
        }
    } catch (error) {
        console.error('Error:', error);
        alert('Σφάλμα επικοινωνίας.');
    }
}

// Share Logic
document.getElementById('btnShareNative').addEventListener('click', async () => {
    const shareData = {
        title: 'Olea AI - Ευφυής Γεωργία',
        text: 'Δες αυτή την απίστευτη εφαρμογή για τη διαχείριση του ελαιώνα!',
        url: window.location.origin
    };
    if (navigator.share) {
        try { await navigator.share(shareData); } catch (err) { console.log('Σφάλμα κοινοποίησης:', err); }
    } else {
        navigator.clipboard.writeText(window.location.origin);
        alert('Το Link αντιγράφηκε στο πρόχειρο!');
    }
});

document.getElementById('btnShowQR').addEventListener('click', () => {
    const qrContainer = document.getElementById('qrContainer');
    const qrImage = document.getElementById('qrImage');
    // Uses a free, reliable external API to generate the QR code instantly based on the current URL
    qrImage.src = 'https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=' + encodeURIComponent(window.location.origin);
    qrContainer.style.display = 'block';
});

function updateTotalTrees(containerId, outputId) {
    let total = 0;
    const container = document.getElementById(containerId);
    if (!container) return;
    const treeInputs = container.querySelectorAll('input[name="poikilia_dentra"]');
    treeInputs.forEach(input => {
        total += parseInt(input.value) || 0;
    });
    const output = document.getElementById(outputId);
    if (output) output.value = total;
}

// --- ΝΕΑ ΛΟΓΙΚΗ ΓΙΑ ΔΥΝΑΜΙΚΕΣ ΠΟΙΚΙΛΙΕΣ ---
function addVarietyRow(containerId, totalOutputId = null) {
    const container = document.getElementById(containerId);
    if (!container) return;
    const newRow = document.createElement('div');
    newRow.className = 'input-group input-group-sm mb-2';
    
    let onInputAttr = '';
    if (totalOutputId) {
        onInputAttr = `oninput="updateTotalTrees('${containerId}', '${totalOutputId}')"`;
    }
    
    newRow.innerHTML = `
        <select name="poikilia_onoma" class="form-select form-select-sm" required style="max-width: 30%;">
            <option value="" disabled selected>Επιλέξτε ποικιλία...</option>
            <option value="Κορωνέικη">Κορωνέικη</option>
            <option value="Καλαμών">Καλαμών</option>
            <option value="Χαλκιδικής">Χαλκιδικής</option>
            <option value="Μανάκι">Μανάκι</option>
            <option value="Αθηνοελιά">Αθηνοελιά</option>
            <option value="Μεγαρίτικη">Μεγαρίτικη</option>
            <option value="Άλλη">Άλλη</option>
        </select>
        <select name="poikilia_ilikia" class="form-select form-select-sm" required style="max-width: 35%;">
            <option value="" disabled selected>Ηλικία...</option>
            <option value="Νεαρά (1-5 ετών)">1-5 ετών</option>
            <option value="Παραγωγικά (6-30 ετών)">6-30 ετών</option>
            <option value="Γηραιά (30+ ετών)">30+ ετών</option>
        </select>
        <input type="number" name="poikilia_dentra" class="form-control form-control-sm" placeholder="Αριθμός" ${onInputAttr} style="max-width: 90px;" required>
        <button class="btn btn-outline-danger" type="button" onclick="this.parentElement.remove(); ${totalOutputId ? `updateTotalTrees('${containerId}', '${totalOutputId}')` : ''}"><i class="fas fa-times"></i></button>
    `;
    container.appendChild(newRow);
}

// Global function to handle AI task confirmation from other places (like refine)
window.confirmAIErgasies = async function(ktimaId, ergasies) {
    if (ergasies && ergasies.length > 0) {
        let msg = "Ο AI Γεωπόνος προτείνει τις εξής εργασίες:\n";
        ergasies.forEach(e => {
            msg += `- ${e.eidos} (${e.farmaka || 'Χωρίς υλικά'})\n`;
        });
        msg += "\nΘέλετε να αντικαταστήσετε τις τρέχουσες εκκρεμείς εργασίες σας με αυτές;";
        
        if (confirm(msg)) {
            await fetch('/epivevaiosi_ergasion_ai/' + ktimaId, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ ergasies: ergasies })
            });
            sessionStorage.setItem('reopenModal', 'modalAnalytiki' + ktimaId);
            sessionStorage.setItem('scrollToSyntages', ktimaId);
            location.reload();
        }
    }
};

// --- AJAX Toggle Καλλιέργειας (Αποτροπή Web View Refresh) ---
async function toggleKalliergeia(ktimaId, btnEl) {
    const originalHtml = btnEl.innerHTML;
    btnEl.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
    btnEl.disabled = true;
    
    try {
        const response = await fetch('/toggle_kalliergeia/' + ktimaId, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest'
            }
        });
        const data = await response.json();
        
        if (data.success) {
            const isBio = data.neos_typos === 'Βιολογική';
            btnEl.className = `badge border-0 ${isBio ? 'bg-success' : 'bg-primary'} shadow-sm`;
            btnEl.innerHTML = `<i class="fas ${isBio ? 'fa-leaf' : 'fa-tractor'}"></i> <span class="text-label">${data.neos_typos}</span>`;
        } else {
            btnEl.innerHTML = originalHtml;
        }
    } catch (e) {
        console.error('Toggle error:', e);
        btnEl.innerHTML = originalHtml;
    }
    btnEl.disabled = false;
}

// --- NDVI & Satellite Layer Management ---
window.setupSatelliteLayers = function(map, bounds, data, mapId) {
    const ktimaId = mapId.replace('ndviMap', '').replace('analytikiMapModal', '').replace('analytikiMapGeoponos', '');
    
    // Πρώτα ψάχνουμε αν υπάρχει layerControls ειδικά για αυτό τον χάρτη
    let layerControls = document.getElementById('layerControls' + mapId);
    if (!layerControls) {
        // Αν όχι, χρησιμοποιούμε το γενικό του modal
        layerControls = document.getElementById('layerControls' + ktimaId);
    }
    
    if(window.ndviMapOverlays && window.ndviMapOverlays[mapId]) {
        map.removeLayer(window.ndviMapOverlays[mapId]);
    }
    
    if (!window.ndviMapOverlays) window.ndviMapOverlays = {};
    
    // Προσθήκη του προεπιλεγμένου (NDVI) overlay
    if (data.ndvi_url) {
        let overlay = L.imageOverlay(data.ndvi_url, bounds).addTo(map);
        window.ndviMapOverlays[mapId] = overlay;
    }

    // Δημιουργία των κουμπιών επιλογής
    if (layerControls) {
        layerControls.innerHTML = '';
        const createBtn = (text, url, colorClass) => {
            if (!url) return '';
            return `<button type="button" class="btn btn-sm ${colorClass} me-1 mb-1 shadow-sm" onclick="changeMapLayer('${mapId}', '${url}', '${ktimaId}')">${text}</button>`;
        };

        let buttonsHtml = '';
        buttonsHtml += createBtn('NDVI (Βλάστηση)', data.ndvi_url, 'btn-success');
        buttonsHtml += createBtn('NDWI (Υγρασία)', data.ndwi_url, 'btn-info text-white');
        buttonsHtml += createBtn('EVI (Βλάστηση+)', data.evi_url, 'btn-primary');
        buttonsHtml += createBtn('Φυσικό Χρώμα', data.truecolor_url, 'btn-secondary');
        buttonsHtml += createBtn('Ψευδές Χρώμα', data.falsecolor_url, 'btn-warning text-dark');
        
        // Προσθήκη κουμπιού για Οδηγό Ανάγνωσης
        buttonsHtml += `<button type="button" class="btn btn-sm btn-outline-dark mb-1 shadow-sm ms-1" data-bs-toggle="modal" data-bs-target="#modalMapLegend"><i class="fas fa-question-circle"></i> Τι σημαίνουν τα χρώματα;</button>`;

        layerControls.innerHTML = buttonsHtml;
        layerControls.classList.remove('d-none');
    }
};

window.changeMapLayer = function(mapId, url, ktimaId) {
    let map = (window.initializedMaps && window.initializedMaps[mapId]) ? window.initializedMaps[mapId] : (window.analytikiMaps && window.analytikiMaps[mapId] ? window.analytikiMaps[mapId] : null);
    let bounds = window.ndviMapBounds ? window.ndviMapBounds[ktimaId] : null;
    
    if (map && bounds && url) {
        if(window.ndviMapOverlays && window.ndviMapOverlays[mapId]) {
            map.removeLayer(window.ndviMapOverlays[mapId]);
        }
        let overlay = L.imageOverlay(url, bounds).addTo(map);
        window.ndviMapOverlays[mapId] = overlay;
    }
};

// --- UX Βελτιώσεις για Κινητά & PWA (Διατήρηση θέσης οθόνης) ---
document.addEventListener("DOMContentLoaded", function() {
    // 1. Επαναφορά θέσης scroll
    const savedPath = sessionStorage.getItem('scrollPath');
    const scrollPos = sessionStorage.getItem('scrollPosition');
    
    if (savedPath === window.location.pathname && scrollPos) {
        // Μικρή καθυστέρηση για να προλάβουν να φορτώσουν τα στοιχεία της σελίδας
        setTimeout(() => {
            window.scrollTo({ top: parseInt(scrollPos), behavior: 'auto' });
        }, 100);
    }
    
    // 2. Επαναφορά ανοιχτού Κτήματος (Αν χρησιμοποιείς Bootstrap Accordion/Collapse)
    const openCollapseId = sessionStorage.getItem('openCollapseId');
    if (openCollapseId && savedPath === window.location.pathname) {
        const collapseEl = document.getElementById(openCollapseId);
        if (collapseEl && typeof bootstrap !== 'undefined' && !collapseEl.classList.contains('show')) {
            new bootstrap.Collapse(collapseEl, { toggle: true });
        }
    }

    // Παρακολούθηση ανοίγματος/κλεισίματος για να θυμόμαστε τι βλέπει ο χρήστης
    document.querySelectorAll('.collapse').forEach(function(el) {
        el.addEventListener('shown.bs.collapse', function (e) {
            if (e.target.id) sessionStorage.setItem('openCollapseId', e.target.id);
            
            // Βελτιστοποίηση: Όταν ανοίγει ένα κτήμα, "ξυπνάμε" τον χάρτη ακαριαία (invalidateSize) 
            // για να μην εμφανίζει "γκρι κουτάκια" και να προφορτώνει τα πλακίδια (tiles).
            setTimeout(() => {
                const maps = Object.assign({}, window.initializedMaps || {}, window.analytikiMaps || {});
                for (let mapId in maps) {
                    let map = maps[mapId];
                    if (map && map._container && e.target.contains(map._container)) {
                        map.invalidateSize();
                    }
                }
            }, 50);
        });
        el.addEventListener('hidden.bs.collapse', function (e) {
            if (e.target.id === sessionStorage.getItem('openCollapseId')) {
                sessionStorage.removeItem('openCollapseId');
            }
        });
    });
});

window.addEventListener("beforeunload", function() {
    // Αποθήκευση της θέσης scroll πριν την ανανέωση ή υποβολή φόρμας
    sessionStorage.setItem('scrollPath', window.location.pathname);
    sessionStorage.setItem('scrollPosition', window.scrollY);
});

// --- FIX: Αποτροπή αναπήδησης (Jump) του χάρτη πάνω-αριστερά στα κινητά ---
let isMapDraggingGlobal = false;
let dragTimerGlobal;

// --- ΒΕΛΤΙΣΤΟΠΟΙΗΣΗ ΤΑΧΥΤΗΤΑΣ & CACHE ΧΑΡΤΗ ---
if (typeof L !== 'undefined' && L.TileLayer) {
    L.TileLayer.mergeOptions({
        keepBuffer: 4,             // Διατήρηση 4x περισσότερων πλακιδίων στη μνήμη (ταχύτερη επιστροφή στο ίδιο σημείο)
        updateWhenIdle: true,      // Φόρτωση νέων κομματιών χάρτη ΜΟΝΟ όταν σταματάς να τον σέρνεις (αποτρέπει κολλήματα)
        updateWhenZooming: false   // Σταματάει τη λήψη εικόνων κατά τη διάρκεια του Zoom animation
    });
}

if (typeof L !== 'undefined' && L.Map) {
    // Απενεργοποιούμε το προεπιλεγμένο 'tap' του Leaflet που προκαλεί το bug σε οθόνες αφής
    L.Map.addInitHook(function () {
        if (L.Browser.mobile) {
            this.options.tap = false;
        }
        
        // Παρακολούθηση συρσίματος (drag) για αποτροπή τυχαίων κλικ
        this.on('dragstart', function() { isMapDraggingGlobal = true; });
        this.on('dragend', function() {
            clearTimeout(dragTimerGlobal);
            dragTimerGlobal = setTimeout(() => { isMapDraggingGlobal = false; }, 400); // Προστασία/κλείδωμα κλικ για 400ms μετά το σύρσιμο
        });
    });
}

// Μπλοκάρουμε το 'click' (πριν φτάσει στο εργαλείο σχεδίασης) αμέσως μετά από σύρσιμο του χάρτη!
document.addEventListener('click', function(e) {
    if (isMapDraggingGlobal && e.target && typeof e.target.closest === 'function') {
        if (e.target.closest('.leaflet-container')) {
            e.stopPropagation();
            e.preventDefault();
        }
    }
}, true); // Το true σημαίνει Capture phase (το πιάνει πρώτο από όλους)

document.addEventListener("DOMContentLoaded", function() {
    const leafletTouchFix = document.createElement('style');
    leafletTouchFix.innerHTML = ".leaflet-container { touch-action: none !important; -webkit-tap-highlight-color: transparent; }";
    document.head.appendChild(leafletTouchFix);
});

// --- FIX: Αποτροπή εσωτερικού scroll (Jumping) του χάρτη στην πάνω-αριστερή γωνία κατά τη σχεδίαση (Leaflet.Draw bug) ---
document.addEventListener('scroll', function(e) {
    if (e.target && e.target.classList && e.target.classList.contains('leaflet-container')) {
        e.target.scrollTop = 0;
        e.target.scrollLeft = 0;
    }
}, true);