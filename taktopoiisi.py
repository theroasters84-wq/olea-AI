import os
import shutil

def taktopoiisi_arxeiwn():
    # Ο φάκελος που πρέπει να μπουν τα αρχεία
    fakelos_efarmogi = "efarmogi"
    
    # Λίστα με τα αρχεία που πρέπει να μετακινηθούν
    arxeia = ["__init__.py", "montela.py", "dromologia.py"]
    
    # Δημιουργία του φακέλου αν δεν υπάρχει
    if not os.path.exists(fakelos_efarmogi):
        os.makedirs(fakelos_efarmogi)
        print(f"Δημιουργήθηκε ο φάκελος '{fakelos_efarmogi}'")
        
    # Μετακίνηση αρχείων
    for arxeio in arxeia:
        if os.path.exists(arxeio):
            dst = os.path.join(fakelos_efarmogi, arxeio)
            shutil.move(arxeio, dst)
            print(f"✅ Μετακινήθηκε το '{arxeio}' μέσα στο '{fakelos_efarmogi}'")
        else:
            print(f"⚠️ Το '{arxeio}' δεν βρέθηκε (ίσως είναι ήδη στη θέση του).")

if __name__ == "__main__":
    taktopoiisi_arxeiwn()