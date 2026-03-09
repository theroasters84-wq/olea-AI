import os

arxeio_vasis = "vasi_dedomenwn.db"

if os.path.exists(arxeio_vasis):
    try:
        os.remove(arxeio_vasis)
        print("✅ Η βάση δεδομένων διαγράφηκε επιτυχώς!")
        print("Τώρα τρέξτε το 'py efarmogi.py' για να δημιουργηθεί η καινούργια.")
    except PermissionError:
        print("❌ ΣΦΑΛΜΑ: Δεν μπορώ να διαγράψω το αρχείο.")
        print("⚠️ ΠΡΟΣΟΧΗ: Πρέπει πρώτα να κλείσετε τον server (πατήστε Ctrl+C)!")
else:
    print("⚠️ Δεν βρέθηκε αρχείο βάσης δεδομένων. Όλα καλά, ξεκινήστε την εφαρμογή.")