from pq_ntru.NTRUencrypt import NTRUencrypt
from pq_ntru.NTRUdecrypt import NTRUdecrypt
from pq_ntru.NTRUutil import factor_int
import time

prog_description = """

An implementation of the NTRU encryption algorithm in python3.

Based on the original NTRU paper by Hoffstein, Pipher and Silverman [1].

"""

prog_epilog = """

References:
[1] Hoffstein J, Pipher J, Silverman JH. NTRU: A Ring-Based Public Key Cryptosystem. In: International Algorithmic Number Theory Symposium. Springer; 1998. p. 267--288.

"""


def generate_keys(name="key", mode="highest", skip_check=False, debug=False):
    if mode not in ["moderate", "high", "highest"]:
        raise ValueError("Input string must be 'moderate', 'high', or 'highest'")
    """
    :param name: name of file output
    :param mode: moderate, high, highest
    :return:
    """
    if debug:
        finished = False
        print("[i] Starting generation...")
        for i in range(10):
            print(f"[i] Round {i}/10 of key generation started")
            N1 = NTRUdecrypt()
            print("[i] Initialised function.")
            print("Choosing mode:", mode)
            if mode == "moderate":
                N1.setNpq(N=107, p=3, q=64, df=15, dg=12, d=5)
            elif mode == "high":
                N1.setNpq(N=167, p=3, q=128, df=61, dg=20, d=18)
            elif mode == "highest":
                N1.setNpq(N=503, p=3, q=256, df=216, dg=72, d=55)

            print("[i] Generating keys")
            N1.genPubPriv(name)
            print("[i] Created.")

            if skip_check:
                finished = True
                print("[-] Skipping security check")
                break

            print("[i] Getting factors:")
            factors = factor_int(N1.h[-1])
            print("[i] Factors:", factors)
            possible_keys = 2 ** N1.df * (N1.df + 1) ** 2 * 2 ** N1.dg * (N1.dg + 1) * 2 ** N1.dr * (N1.dr + 1)
            print("[i] Checking if key is long enough.")
            if len(factors) == 0 and possible_keys > 2**80:  # see 'security_check.py' for more information
                print("Security passed")
                finished = True
                break
            else:
                print("[-] Security check not passed. Trying again.")
        if not finished:
            print("[-] Couldn't generate key, as security couldn't be verified in 10 checks.")
        print("[+] Done.")
    else:
        finished = False
        for i in range(10):
            N1 = NTRUdecrypt()
            if mode == "moderate":
                N1.setNpq(N=107, p=3, q=64, df=15, dg=12, d=5)
            elif mode == "high":
                N1.setNpq(N=167, p=3, q=128, df=61, dg=20, d=18)
            elif mode == "highest":
                N1.setNpq(N=503, p=3, q=256, df=216, dg=72, d=55)

            # N1.setNpq(N=503, p=3, q=2048, df=216, dg=72, d=55)
            N1.setNpq(N=503, p=3, q=2048, df=216, dg=72, d=55)

            # print("ye")

            """
            N: Primzahl. Je höher die Primzahl, desto mehr Sicherheit wird garantiert.
            p: Ebenfalls eine Primzahl.
            q: Bit-Größe der Verschlüsselung. Sehr wichtig um Sicherheit zu garantieren. 
            df: Maximale Anzahl von Koeffizienten in einem Polynom. df = dual Fehler. Je größer, desto mehr Sicherheit. Normal: 100 - 500.
            dg: Anzahl der Koeffizienten in einem Polynom `g` und `g`.
            d: Schlüsselgrad. Bestimmt die Länge des geheimen Schlüssels.
            
            p und q müssen teilerfremd sein.
            q muss größer als p sein.
            
            f: Ein Polynom, das in der Regel zufällig gewählt wird. Es hat Grad N und ist definiert über dem Ring R.
            fp: Ein Polynom, der das Inverse von f modulo p ist. p ist eine große Primzahl.
            fq: Ein Polynom, der das Inverse von f modulo q ist. q ist eine große Primzahl, die 1 modulo N ist.
            g: Ein weiteres Polynom, das in der Regel zufällig gewählt wird. Es hat Grad N und ist definiert über dem Ring R.
            h: Das Geheimnis, das verschlüsselt werden soll. Es ist ein Polynom mit Grad N-1 und Koeffizienten, die aus {0, 1, -1} gewählt werden.
            I: Die Einheitsmatrix der Größe N-1.
            """

            N1.genPubPriv(name)

            if skip_check:
                finished = True
                break

            factors = factor_int(N1.h[-1])
            possible_keys = 2 ** N1.df * (N1.df + 1) ** 2 * 2 ** N1.dg * (N1.dg + 1) * 2 ** N1.dr * (N1.dr + 1)
            if len(factors) == 0 and possible_keys > 2**80:  # see 'security_check.py' for more information
                finished = True
                break
            print("failed")
        if not finished:
            print("[-] Security of keys couldn't get verified.")


def encrypt(name: str, string: str):
    """
    :param name: name of key file
    :param string: message to encrypt as a string
    :return:
    """
    E = NTRUencrypt()
    E.readPub(name + ".pub")
    E.encryptString(string)

    return E.Me


def decrypt(name: str, cipher: str):
    """
    :param name: name of key file
    :param cipher: encrypted message
    :return:
    """
    D = NTRUdecrypt()
    D.readPriv(name + ".priv")
    to_decrypt = cipher
    D.decryptString(to_decrypt)

    return D.M


def generate_keys_ntru(name="key", mode="highest", skip_check=False, debug=False):
    if mode not in ["moderate", "high", "highest"]:
        raise ValueError("Input string must be 'moderate', 'high', or 'highest'")
    """
    :param name: name of file output
    :param mode: moderate, high, highest
    :return:
    """
    if debug:
        finished = False
        print("[i] Starting generation...")
        for i in range(10):
            print(f"[i] Round {i}/10 of key generation started")
            N1 = NTRUdecrypt()
            print("[i] Initialised function.")
            print("Choosing mode:", mode)
            if mode == "moderate":
                N1.setNpq(N=107, p=3, q=64, df=15, dg=12, d=5)
            elif mode == "high":
                N1.setNpq(N=167, p=3, q=128, df=61, dg=20, d=18)
            elif mode == "highest":
                N1.setNpq(N=503, p=3, q=256, df=216, dg=72, d=55)

            print("[i] Generating keys")
            N1.genPubPriv(name)
            print("[i] Created.")

            if skip_check:
                finished = True
                print("[-] Skipping security check")
                break

            print("[i] Getting factors:")
            factors = factor_int(N1.h[-1])
            print("[i] Factors:", factors)
            possible_keys = 2 ** N1.df * (N1.df + 1) ** 2 * 2 ** N1.dg * (N1.dg + 1) * 2 ** N1.dr * (N1.dr + 1)
            print("[i] Checking if key is long enough.")
            if len(factors) == 0 and possible_keys > 2 ** 80:  # see 'security_check.py' for more information
                print("Security passed")
                finished = True
                break
            else:
                print("[-] Security check not passed. Trying again.")
        if not finished:
            print("[-] Couldn't generate key, as security couldn't be verified in 10 checks.")
        print("[+] Done.")
    else:
        finished = False
        for i in range(10):
            N1 = NTRUdecrypt()
            if mode == "moderate":
                N1.setNpq(N=107, p=3, q=2048, df=15, dg=12, d=5)
            elif mode == "high":
                N1.setNpq(N=167, p=3, q=2048, df=61, dg=20, d=18)
            elif mode == "highest":
                N1.setNpq(N=503, p=3, q=2048, df=216, dg=72, d=55)


            N1.generate_keys_with_rsa(name)

            if skip_check:
                finished = True
                break

            factors = factor_int(N1.h[-1])
            possible_keys = 2 ** N1.df * (N1.df + 1) ** 2 * 2 ** N1.dg * (N1.dg + 1) * 2 ** N1.dr * (N1.dr + 1)
            if len(factors) == 0 and possible_keys > 2 ** 80:  # see 'security_check.py' for more information
                finished = True
                break
            print("failed")
        if not finished:
            print("[-] Security of keys couldn't get verified.")


def encrypt_rsa(name: str, string: str):
    E = NTRUencrypt()
    E.read_pub_rsa(name + ".pub")
    E.encrypt_string_rsa(string)

    return E.Me


def decrypt_rsa(name: str, cipher: str):
    N1 = NTRUdecrypt()
    N1.read_rsa_priv(filename=name+".priv")
    N1.decrypt_with_rsa(cipher)
    return N1.M
