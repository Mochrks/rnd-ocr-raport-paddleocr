from app.services.fuzzy.base_matcher import fuzzy_match


OCCUPATIONS = [

    "PEGAWAI NEGERI SIPIL (PNS)",
    "TENTARA NASIONAL INDONESIA (TNI)",
    "KEPOLISIAN RI (POLRI)",
    "ANGGOTA DPR-RI",
    "ANGGOTA DPD",
    "ANGGOTA BPK",
    "PRESIDEN",
    "WAKIL PRESIDEN",
    "ANGGOTA MAHKAMAH KONSTITUSI",
    "ANGGOTA KABINET/KEMENTERIAN",
    "DUTA BESAR/KEPALA PERWAKILAN",
    "GUBERNUR",
    "WAKIL GUBERNUR",
    "BUPATI",
    "WAKIL BUPATI",
    "WALIKOTA",
    "WAKIL WALIKOTA",
    "ANGGOTA DPRD PROPINSI",
    "ANGGOTA DPRD KABUPATEN/KOTA",
    "ANGGOTA LEMBAGA TINGGI LAINNYA",
    "PERANGKAT DESA",
    "KEPALA DESA",

    "PETANI/PEKEBUN",
    "PETERNAK",
    "NELAYAN/PERIKANAN",
    "BURUH TANI/PERKEBUNAN",
    "BURUH NELAYAN/PERIKANAN",
    "BURUH PETERNAKAN",

    "INDUSTRI",
    "KONSTRUKSI",
    "TENAGA TATA USAHA",
    "BURUH HARIAN LEPAS",
    "PEKERJA PENGOLAHAN, KERAJINAN",
    "MEKANIK",
    "TEKNISI",
    "OPERATOR",
    "PILOT",
    "PELAUT",
    "SOPIR",
    "TRANSPORTASI",

    "PERDAGANGAN",
    "KARYAWAN SWASTA",
    "KARYAWAN BUMN",
    "KARYAWAN BUMD",
    "KARYAWAN HONORER",
    "WIRASWASTA",
    "PEDAGANG",
    "PIALANG",
    "MANAJER",
    "KONSULTAN",
    "PENGACARA",
    "NOTARIS",
    "AKUNTAN",
    "PENTERJEMAH",

    "PEMBANTU RUMAH TANGGA",
    "TUKANG CUKUR",
    "TUKANG LISTRIK",
    "TUKANG BATU",
    "TUKANG KAYU",
    "TUKANG SOL SEPATU",
    "TUKANG LAS/PANDAI BESI",
    "TUKANG JAHIT",
    "TUKANG GIGI",
    "PENATA RIAS",
    "PENATA BUSANA",
    "PENATA RAMBUT",
    "JURU MASAK",
    "CHEF",

    "DOSEN",
    "GURU",
    "PENELITI",
    "ASISTEN AHLI",

    "BIDAN",
    "PERAWAT",
    "APOTEKER",
    "DOKTER",
    "PSIKIATER/PSIKOLOG",
    "TABIB",
    "PARAJI",

    "SENIMAN",
    "PERANCANG BUSANA",
    "WARTAWAN",
    "ARTIS",
    "PENYIAR TELEVISI",
    "PENYIAR RADIO",
    "PROMOTOR ACARA",
    "ARSITEK",

    "IMAM MASJID",
    "PENDETA",
    "PASTOR",
    "USTADZ/MUBALIGH",
    "BIARAWATI",
    "PARANORMAL",

    "ATLET",

    "BELUM/TIDAK BEKERJA",
    "MENGURUS RUMAH TANGGA",
    "PELAJAR/MAHASISWA",
    "PENSIUNAN"
]


def match_occupation(value):

    return fuzzy_match(
        value=value,
        choices=OCCUPATIONS,
        score_cutoff=65
    )
