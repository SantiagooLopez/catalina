"""Public portal guidance; never queries the institutional corpus or directory."""
import re
import unicodedata

from catalina_ingestion.services.conversation_routing import conversational_reply


def public_reply(query: str) -> tuple[str, str]:
    text = ''.join(c for c in unicodedata.normalize('NFKD', query.casefold())
                   if not unicodedata.combining(c))
    text = ' '.join(re.sub(r'[^a-z0-9\s]', ' ', text).split())
    # Curated public guidance, verified against the official admissions portal.
    # This does not unlock the institutional corpus or the campus directory.
    if re.search(r'\b(precios?|costos?|cuanto cuesta|cuanto vale|valor|tarifas?)\b', text):
        return ('Para conocer el valor de matrícula y los costos aplicables a tu caso, '
                'acércate a Registro y Control Académico para recibir orientación y confirmar '
                'el trámite con el área correspondiente. No puedo cotizar un valor sin una '
                'tarifa oficial vigente. También puedes solicitar orientación en '
                'https://admisiones.ucatolica.edu.co/.', 'public_guidance')
    if re.search(r'\b(carreras?|programas?|pregrados?|oferta academica)\b', text) and re.search(r'\b(que|cuales|ofrece|tiene|hay|conocer)\b', text):
        return ('La oferta pública de pregrado incluye Arquitectura, Derecho, Economía, '
                'Psicología, Administración de Empresas e Inteligencia de Negocios, '
                'Ingeniería Civil, Ingeniería Industrial, Ingeniería de Sistemas y Computación '
                'e Ingeniería de Datos e Inteligencia Artificial. Consulta cada programa, '
                'sus requisitos y disponibilidad en el portal oficial: '
                'https://admisiones.ucatolica.edu.co/pregrado/.', 'public_guidance')
    if re.search(r'\b(matricular\w*|inscrib\w*|admision\w*|inscripcion\w*)\b', text) and re.search(r'\b(donde|como|quiero|puedo)\b', text):
        return ('Si eres aspirante, empieza por el portal oficial de Admisiones: '
                'https://admisiones.ucatolica.edu.co/. Elige el programa y sigue el proceso '
                'de inscripción y admisión; la matrícula se formaliza después de cumplir '
                'los requisitos. Puedes pedir orientación en admisiones@ucatolica.edu.co. '
                'Si ya eres estudiante, consulta el PAW y confirma tu trámite con Registro '
                'y Control Académico. Para documentos y ubicaciones dentro de Catalina, inicia sesión.',
                'public_guidance')
    if re.fullmatch(r'(quien eres|que puedes hacer|como funciona(?: esta pagina)?|que es catalina|ayuda)(?: catalina)?', text):
        return ('Soy Catalina, un prototipo académico de asistencia universitaria. '
                'Aquí puedes conocer cómo usar la página. Inicia sesión en Mi espacio '
                'para consultar documentos con fuentes, guardar conversaciones y explorar el mapa del campus.',
                'public_guidance')
    if re.fullmatch(r'(como (?:inicio sesion|ingreso|accedo)|donde inicio sesion)', text):
        return ('Selecciona Mi espacio o amplía el chat e ingresa con tu correo y contraseña. '
                'Con tu sesión podrás consultar documentos, conversaciones y ubicaciones del campus.',
                'public_guidance')
    reply = conversational_reply(query)
    if reply and re.fullmatch(r'(hola|buenas|buenos dias|buenas tardes|buenas noches|hey|que tal|como estas|como te va|gracias|muchas gracias|adios|hasta luego|chao|nos vemos|ok|vale|perfecto|entendido)(?: catalina)?(?: como estas| como te va| por tu ayuda)?', text):
        return reply, 'conversational'
    return ('Para consultar documentos institucionales, trámites o ubicaciones del campus, '
            'inicia sesión en Mi espacio o amplía el chat. Sin sesión puedo explicarte '
            'qué es Catalina y cómo utilizar esta página.', 'authentication_required')
