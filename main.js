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

function completeTask(ktimaId, taskName) {
    // STEP 1: Έλεγχος για προτροπή αυτόματης καταγραφής (AI Auto-Log)
    const keywords = ['Ψεκασμός', 'Λίπανση', 'Φάρμακο', 'Χαλκό', 'Σκεύασμα'];
    const isChemicalTask = keywords.some(kw => taskName.toLowerCase().includes(kw.toLowerCase()));

    if (isChemicalTask) {
        if (confirm("Θέλετε να βγάλετε φωτογραφία την ετικέτα από το μπουκάλι/σακί για αυτόματη καταγραφή στο ψηφιακό αρχείο;")) {
            // Προγραμματιστικό άνοιγμα της κάμερας από το αντίστοιχο modal
            const modal = document.getElementById('modalErgasies' + ktimaId);
            const fileInput = modal.querySelector('form[action*="ai_input_scan"] input[type="file"]');
            if (fileInput) {
                fileInput.click();
                return; // Διακοπή της χειροκίνητης ολοκλήρωσης
            }
        }
    }

    let cost = prompt('Ποιο ήταν το κόστος αυτής της εργασίας; (Βάλτε 0 αν δεν υπήρχε έξοδο)', '0');
    if (cost === null) return; // Cancelled
    
    // Create a form dynamically to submit
    let form = document.createElement('form');
    form.method = 'POST';
    form.action = '/oloklirosi_ergasias/' + ktimaId;
    
    let fieldTask = document.createElement('input'); fieldTask.type = 'hidden'; fieldTask.name = 'eidos_ergasias'; fieldTask.value = taskName;
    let fieldCost = document.createElement('input'); fieldCost.type = 'hidden'; fieldCost.name = 'kostos'; fieldCost.value = cost;
    
    form.appendChild(fieldTask);
    form.appendChild(fieldCost);
    document.body.appendChild(form);
    form.submit();
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
        <select name="poikilia_onoma" class="form-select" required>
            <option value="" disabled selected>Επιλέξτε ποικιλία...</option>
            <option value="Κορωνέικη">Κορωνέικη</option>
            <option value="Καλαμών">Καλαμών</option>
            <option value="Χαλκιδικής">Χαλκιδικής</option>
            <option value="Μανάκι">Μανάκι</option>
            <option value="Αθηνοελιά">Αθηνοελιά</option>
            <option value="Μεγαρίτικη">Μεγαρίτικη</option>
            <option value="Άλλη">Άλλη</option>
        </select>
        <input type="number" name="poikilia_dentra" class="form-control" placeholder="Δέντρα" ${onInputAttr} style="max-width: 100px;" required>
        <button class="btn btn-outline-danger" type="button" onclick="this.parentElement.remove(); ${totalOutputId ? `updateTotalTrees('${containerId}', '${totalOutputId}')` : ''}"><i class="fas fa-times"></i></button>
    `;
    container.appendChild(newRow);
}