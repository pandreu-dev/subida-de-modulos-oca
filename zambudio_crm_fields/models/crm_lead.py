# -*- coding: utf-8 -*-
"""Campos de Studio de crm.lead adoptados como codigo.

Definiciones EXACTAS (tipo, relacion, valores de selection) segun la foto de PRE,
para adoptarlos sin tocar las columnas ni los datos. Los 2 campos que en Studio
eran CALCULADOS (fecha_fin_contrato, ingreso_ponderado) se adoptan como campos
normales: conservan su valor actual y la logica real la llevan las automatizaciones
de CRM (zambudio_crm_automations). Decision de negocio (Laura): replicar; los datos
pueden perderse (aqui de hecho se conservan).
"""
from odoo import fields, models

# Listas de valores de los selection (claves == valores guardados en PRE).
PEOPLE = [
    ("Sergio Almendros", "Sergio Almendros"),
    ("Mariano Lamo", "Mariano Lamo"),
    ("Maria Jesús Conesa", "Maria Jesús Conesa"),
    ("Alberto Soler", "Alberto Soler"),
    ("Antonio Soler", "Antonio Soler"),
    ("Mauricio Cánovas", "Mauricio Cánovas"),
    ("Alejo López", "Alejo López"),
    ("Carlos Clemente", "Carlos Clemente"),
    ("Efrén Sánchez", "Efrén Sánchez"),
    ("Raúl González", "Raúl González"),
    ("Odoo Partnership", "Odoo Partnership"),
]
DIVISION = [
    ("NODO RENOVABLES", "NODO RENOVABLES"),
    ("SELECT ASTERISCO", "SELECT ASTERISCO"),
    ("NODO COMUNICACIONES", "NODO COMUNICACIONES"),
    ("BPO", "BPO"),
    ("DIGITAL", "DIGITAL"),
]
PRACTICA = [
    ("AI&DATA", "AI&DATA"),
    ("SOFTWARE", "SOFTWARE"),
    ("T&M", "T&M"),
    ("AUTOMATION", "AUTOMATION"),
    ("EAP", "EAP"),
]
TAMANO = [
    ("Autónomo", "Autónomo"),
    ("PYME", "PYME"),
    ("Gran empresa", "Gran empresa"),
    ("Público", "Público"),
]
PROB_INICIAL = [("0%", "0%"), ("10%", "10%"), ("30%", "30%")]
PROB_AVANZADA = [("0%", "0%"), ("10%", "10%"), ("30%", "30%"), ("60%", "60%"), ("90%", "90%")]
PROB_NEGOCIACION = [("30%", "30%"), ("60%", "60%"), ("90%", "90%")]


class CrmLead(models.Model):
    _inherit = "crm.lead"

    # --- Comercial / responsable ---
    x_studio_comercial = fields.Selection(selection=PEOPLE, string="Comercial")
    x_studio_selection_field_83n_1jiv18ana = fields.Selection(selection=PEOPLE, string="Responsable")
    x_studio_responsable = fields.Char(string="Responsable")

    # --- Clasificacion comercial ---
    x_studio_many2one_field_1nk_1ja0lhri5 = fields.Many2one("x_sector", string="Sector")
    x_studio_tamao = fields.Selection(selection=TAMANO, string="Tamaño")
    x_studio_divisin = fields.Selection(selection=DIVISION, string="División")
    x_studio_prctica = fields.Selection(selection=PRACTICA, string="Práctica")
    x_studio_prctica_relacionada = fields.Many2one("x_crm_practica", string="Práctica (relacionada)")

    # --- Probabilidades / fase ---
    x_studio_probabilidad_inicial = fields.Selection(selection=PROB_INICIAL, string="Probabilidad inicial")
    x_studio_probabilidad_avanzada = fields.Selection(selection=PROB_AVANZADA, string="Probabilidad oferta entregada")
    x_studio_probabilidad_negociacin = fields.Selection(selection=PROB_NEGOCIACION, string="Probabilidad fase negociación")
    x_studio_etapa = fields.Integer(string="Etapa")
    x_studio_etapa_1 = fields.Char(string="Fase")

    # --- Ingresos / margenes ---
    x_studio_ingresos_sos = fields.Monetary(string="Ingresos SoS", currency_field="company_currency")
    x_studio_ingresos_cogs = fields.Monetary(string="Ingresos COGS", currency_field="company_currency")
    x_studio_pm_sos = fields.Float(string="%PM SoS")
    x_studio_pm_cogs = fields.Float(string="%PM COGs")
    # Calculado en Studio -> adoptado como campo normal (conserva valor).
    x_studio_ingreso_ponderado = fields.Integer(string="Ingreso ponderado")

    # --- Contrato / fechas ---
    x_studio_fecha_inicio_contrato = fields.Date(string="Fecha inicio contrato")
    x_studio_meses_de_duracin = fields.Float(string="Duración (meses)")
    x_studio_fecha_fin_de_contrato = fields.Date(string="Fecha fin de contrato")
    # Calculado en Studio -> adoptado como campo normal (conserva valor).
    x_studio_fecha_fin_contrato = fields.Date(string="Fecha fin contrato")
    x_studio_fecha_prevista_de_cierre_1 = fields.Date(string="Fecha prevista de cierre")

    # --- Analitica ---
    x_studio_many2one_field_6tr_1jg75tejm = fields.Many2one("account.analytic.account", string="Cuenta analítica")
    x_studio_distribucin_analitica = fields.Many2one("account.analytic.distribution.model", string="Distribución analítica")
