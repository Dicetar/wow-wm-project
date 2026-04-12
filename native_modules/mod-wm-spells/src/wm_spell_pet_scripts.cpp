#include "Pet.h"
#include "PetScript.h"
#include "wm_spell_runtime.h"

class wm_spells_pet_script : public PetScript
{
public:
    wm_spells_pet_script() : PetScript("wm_spells_pet_script")
    {
    }

    void OnPetAddToWorld(Pet* pet) override
    {
        WmSpells::ReapplyBoneboundOverlay(pet);
    }
};

void AddSC_mod_wm_spells_pet_scripts()
{
    new wm_spells_pet_script();
}
