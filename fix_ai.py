import os

filepath = 'ai_tools.py'

try:
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    marker = "@ai_bp.route('/delete_analysi_edafous/<int:analysi_id>', methods=['POST'])"
    
    if marker in content:
        valid_content = content.split(marker)[0]
        clean_last_function = marker + "\n@login_required\ndef delete_analysi_edafous(analysi_id):\n    analysi = vasi.session.get(AnalysiEdafous, analysi_id)\n    if not analysi or analysi.ktima.idioktitis != current_user:\n        flash('Δεν βρέθηκε η ανάλυση ή δεν έχετε δικαίωμα διαγραφής.', 'danger')\n        return redirect(request.referrer or url_for('core_app.arxikh'))\n    \n    vasi.session.delete(analysi)\n    vasi.session.commit()\n    flash('Η ανάλυση εδάφους διαγράφηκε επιτυχώς.', 'success')\n    return redirect(request.referrer or url_for('core_app.arxikh'))\n"
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(valid_content + clean_last_function)
            
        print("✅ Το αρχείο ai_tools.py καθαρίστηκε και διορθώθηκε επιτυχώς!")
    else:
        print("⚠️ Δεν βρέθηκε το σημείο διαχωρισμού. Το αρχείο ίσως είναι ήδη καθαρό.")
except Exception as e:
    print(f"Σφάλμα: {e}")