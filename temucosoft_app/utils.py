import re

def clean_rut(rut):
    """Limpia el RUT de puntos, guiones y espacios, y lo formatea como CUERPO-DV."""
    if not rut:
        return None
    
    rut = str(rut).replace('.', '').replace(' ', '')
    rut = rut.upper()

    if len(rut) < 2:
        return None

    # Separar cuerpo y DV
    if '-' in rut:
        cuerpo, dv = rut.split('-')
    else:
        cuerpo = rut[:-1]
        dv = rut[-1]
    
    if not cuerpo.isdigit() or not (dv.isdigit() or dv == 'K'):
        return None

    return cuerpo + '-' + dv

def is_valid_rut(rut):
    """Implementa el algoritmo de Módulo 11 para validar el RUT chileno."""
    rut_limpio = clean_rut(rut)
    if not rut_limpio:
        return False
        
    try:
        cuerpo, dv_ingresado = rut_limpio.split('-')
        cuerpo_int = int(cuerpo)
    except ValueError:
        return False

    suma = 0
    multiplicador = 2
    temp_cuerpo = cuerpo_int

    while temp_cuerpo > 0:
        suma += (temp_cuerpo % 10) * multiplicador
        temp_cuerpo //= 10
        multiplicador += 1
        if multiplicador == 8:
            multiplicador = 2

    dv_calculado_int = 11 - (suma % 11)
    
    if dv_calculado_int == 10:
        dv_calculado = 'K'
    elif dv_calculado_int == 11:
        dv_calculado = '0'
    else:
        dv_calculado = str(dv_calculado_int)

    return dv_ingresado.upper() == dv_calculado
