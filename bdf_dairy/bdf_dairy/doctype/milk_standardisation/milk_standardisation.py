# Copyright (c) 2026, BDF and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class MilkStandardisation(Document):
	def validate(self):
		seen_priorities = set()
		for row in self.milk_standardisation_silo_details:
			if row.priority in seen_priorities:
				frappe.throw(f"Duplicate Priority {row.priority} is not allowed in Milk Standardisation Silo Details.")
			seen_priorities.add(row.priority)

	def before_save(self):
		total_volume = self.target_volume or 0
		rank = 1
		tot_drawn_volume, milk_fat_mass, milk_snf_mass = 0, 0, 0
		self.milk_standardisation_silo_rank.clear()

		if total_volume <= 0:
			return

		silo_details = sorted(self.milk_standardisation_silo_details, key=lambda x: x.priority)
		for row in silo_details:
			if total_volume <= 0:
				break

			available_volume = row.available_volume or 0
			drawn_volume = min(available_volume, total_volume)
			self.append("milk_standardisation_silo_rank", {
				"rank": rank,
				"silo": row.silo,
				"drawn_volume": drawn_volume
			})
			tot_drawn_volume += drawn_volume
			total_volume -= drawn_volume
			rank += 1

			milk_fat_mass += drawn_volume * row.fat
			milk_snf_mass += drawn_volume * row.snf

		self.milk_used_l = tot_drawn_volume
		self.milk_fat_mass = milk_fat_mass
		self.milk_snf_mass = milk_snf_mass
		self.cream_removed_l = max(0, (milk_fat_mass - (self.target_fat * self.target_volume))/ self.cream_fat)
		self.smp_needed_kg = max(0, ((self.target_volume * self.target_snf) - milk_snf_mass)/ self.smp_snf)
		self.ro_water_needed_l = max(0, self.target_volume - (self.milk_used_l - self.cream_removed_l + self.smp_needed_kg))
		self.final_volume_l = self.milk_used_l - self.cream_removed_l + self.smp_needed_kg + self.ro_water_needed_l
		self.final_fat = (self.milk_fat_mass - self.cream_removed_l * self.cream_fat) / self.final_volume_l
		self.final_snf = (self.milk_snf_mass + self.smp_needed_kg * self.smp_snf) / self.final_volume_l
		self.volume_match = self.final_volume_l - self.target_volume
		self.fat_match = self.final_fat - self.target_fat
		self.snf_match = self.final_snf - self.target_snf